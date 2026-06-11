"""Per-tenant runtime organizations for OpenTrain control-plane tenants."""

import logging
import os

from django.db import transaction
from organizations.models import Organization
from users.models import User
from webhooks.models import Webhook

from .models import BridgeOrganizationLink

logger = logging.getLogger(__name__)

ORG_OWNER_EMAIL_DOMAIN = 'runtime.opentrain.invalid'
ORG_TITLE_MAX_LENGTH = Organization._meta.get_field('title').max_length or 1000


def org_owner_email(opentrain_organization_id):
    return f'ol-org-{opentrain_organization_id}@{ORG_OWNER_EMAIL_DOMAIN}'.lower()


def control_plane_webhook_config():
    """Returns (url, headers) for the OpenTrain control-plane webhook, or (None, None)."""
    base = os.environ.get('OPEN_LABEL_CONTROL_PLANE_BASE_URL', '').strip().rstrip('/')
    if not base:
        return None, None
    headers = {}
    webhook_secret = os.environ.get('OPEN_LABEL_WEBHOOK_SECRET', '').strip()
    if webhook_secret:
        headers['x-open-label-secret'] = webhook_secret
    bypass_token = os.environ.get('OPEN_LABEL_CONTROL_PLANE_BYPASS_TOKEN', '').strip()
    if bypass_token:
        headers['x-vercel-protection-bypass'] = bypass_token
    return f'{base}/api/webhooks/open-label', headers


def ensure_control_plane_webhook(organization):
    """Idempotently maintains the org-level webhook mirroring runtime events to OpenTrain.

    Organization-level (project=None) because PROJECT_CREATED/PROJECT_DELETED are
    organization-only actions that per-project webhooks never receive.
    """
    url, headers = control_plane_webhook_config()
    if not url or organization is None:
        return None
    webhook = Webhook.objects.filter(organization=organization, project__isnull=True, url=url).first()
    if webhook is None:
        return Webhook.objects.create(
            organization=organization,
            project=None,
            url=url,
            headers=headers,
            send_payload=True,
            send_for_all_actions=True,
            is_active=True,
        )
    update_fields = []
    for field, expected in (
        ('headers', headers),
        ('is_active', True),
        ('send_payload', True),
        ('send_for_all_actions', True),
    ):
        if getattr(webhook, field) != expected:
            setattr(webhook, field, expected)
            update_fields.append(field)
    if update_fields:
        webhook.save(update_fields=update_fields)
    return webhook


def ensure_runtime_organization(opentrain_organization_id, title=None):
    """Idempotently resolve (or create) the runtime Organization for an OpenTrain tenant.

    Returns (organization, created). Organization.created_by is a OneToOneField,
    so each tenant org gets its own shadow owner user instead of a shared creator.
    """
    link = (
        BridgeOrganizationLink.objects.select_related('organization')
        .filter(opentrain_organization_id=opentrain_organization_id)
        .first()
    )
    if link:
        ensure_control_plane_webhook(link.organization)
        return link.organization, False

    owner_email = org_owner_email(opentrain_organization_id)
    with transaction.atomic():
        owner = User.objects.filter(email=owner_email).first()
        if owner is None:
            owner = User.objects.create_user(email=owner_email, password=None)
        organization = getattr(owner, 'organization', None)
        if organization is None:
            organization = Organization.create_organization(
                created_by=owner,
                title=(title or f'OpenTrain {opentrain_organization_id}')[:ORG_TITLE_MAX_LENGTH],
            )
        if owner.active_organization_id != organization.id:
            owner.active_organization = organization
            owner.save(update_fields=['active_organization'])
        link, created = BridgeOrganizationLink.objects.get_or_create(
            opentrain_organization_id=opentrain_organization_id,
            defaults={'organization': organization},
        )
    ensure_control_plane_webhook(link.organization)
    return link.organization, created
