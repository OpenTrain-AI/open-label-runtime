"""Shadow runtime users for OpenTrain identities.

Emails stay synthetic; the only profile data the bridge accepts is the
OpenTrain display name, which is already public on the platform.
"""

import logging

from organizations.models import Organization
from users.models import User

from .models import BridgeIdentity

logger = logging.getLogger(__name__)

SHADOW_EMAIL_DOMAIN = 'runtime.opentrain.invalid'


def shadow_email(opentrain_user_id):
    return f'ol-{opentrain_user_id}@{SHADOW_EMAIL_DOMAIN}'.lower()


def ensure_bridge_user(opentrain_user_id, organization=None, display_name=None):
    identity = BridgeIdentity.objects.select_related('user').filter(opentrain_user_id=opentrain_user_id).first()
    if identity:
        user = identity.user
    else:
        email = shadow_email(opentrain_user_id)
        user = User.objects.filter(email=email).first()
        if user is None:
            user = User.objects.create_user(email=email, password=None)
        BridgeIdentity.objects.get_or_create(opentrain_user_id=opentrain_user_id, defaults={'user': user})

    if display_name:
        first_name, _, last_name = display_name.strip().partition(' ')
        first_name = first_name[:256]
        last_name = last_name.strip()[:256]
        if (user.first_name, user.last_name) != (first_name, last_name):
            user.first_name = first_name
            user.last_name = last_name
            user.save(update_fields=['first_name', 'last_name'])

    org = organization or user.active_organization or Organization.objects.first()
    if org is not None:
        org.add_user(user)
        if user.active_organization_id != org.id:
            user.active_organization = org
            user.save(update_fields=['active_organization'])
    return user
