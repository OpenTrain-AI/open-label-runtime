"""Per-tenant runtime organizations for OpenTrain control-plane tenants."""

import logging

from django.db import transaction
from organizations.models import Organization
from users.models import User

from .models import BridgeOrganizationLink

logger = logging.getLogger(__name__)

ORG_OWNER_EMAIL_DOMAIN = 'runtime.opentrain.invalid'
ORG_TITLE_MAX_LENGTH = Organization._meta.get_field('title').max_length or 1000


def org_owner_email(opentrain_organization_id):
    return f'ol-org-{opentrain_organization_id}@{ORG_OWNER_EMAIL_DOMAIN}'.lower()


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
    return link.organization, created
