"""Shadow runtime users for OpenTrain identities. No real PII crosses the bridge."""

import logging

from organizations.models import Organization
from users.models import User

from .models import BridgeIdentity

logger = logging.getLogger(__name__)

SHADOW_EMAIL_DOMAIN = 'runtime.opentrain.invalid'


def shadow_email(opentrain_user_id):
    return f'ol-{opentrain_user_id}@{SHADOW_EMAIL_DOMAIN}'.lower()


def ensure_bridge_user(opentrain_user_id, organization=None):
    identity = BridgeIdentity.objects.select_related('user').filter(opentrain_user_id=opentrain_user_id).first()
    if identity:
        user = identity.user
    else:
        email = shadow_email(opentrain_user_id)
        user = User.objects.filter(email=email).first()
        if user is None:
            user = User.objects.create_user(email=email, password=None)
        BridgeIdentity.objects.get_or_create(opentrain_user_id=opentrain_user_id, defaults={'user': user})

    org = organization or user.active_organization or Organization.objects.first()
    if org is not None:
        org.add_user(user)
        if user.active_organization_id != org.id:
            user.active_organization = org
            user.save(update_fields=['active_organization'])
    return user
