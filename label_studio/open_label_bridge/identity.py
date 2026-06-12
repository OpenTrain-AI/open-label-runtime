"""Shadow runtime users for OpenTrain identities.

Emails stay synthetic; the only profile data the bridge accepts is the
OpenTrain display name and public avatar URL, both already public on the
platform.
"""

import logging

from organizations.models import Organization
from users.models import User

from .models import BridgeIdentity

logger = logging.getLogger(__name__)

SHADOW_EMAIL_DOMAIN = 'runtime.opentrain.invalid'


def shadow_email(opentrain_user_id):
    return f'ol-{opentrain_user_id}@{SHADOW_EMAIL_DOMAIN}'.lower()


AVATAR_URL_MAX_LENGTH = 1024


def normalized_avatar_url(value):
    """Returns a safe https avatar URL or '' (meaning clear); None means leave unchanged."""
    if value is None:
        return None
    if not isinstance(value, str):
        return None
    value = value.strip()
    if value == '':
        return ''
    if not value.lower().startswith('https://') or len(value) > AVATAR_URL_MAX_LENGTH:
        return None
    return value


def ensure_bridge_user(opentrain_user_id, organization=None, display_name=None, avatar_url=None):
    identity = BridgeIdentity.objects.select_related('user').filter(opentrain_user_id=opentrain_user_id).first()
    if identity:
        user = identity.user
    else:
        email = shadow_email(opentrain_user_id)
        user = User.objects.filter(email=email).first()
        if user is None:
            user = User.objects.create_user(email=email, password=None)
        BridgeIdentity.objects.get_or_create(opentrain_user_id=opentrain_user_id, defaults={'user': user})

    update_fields = []
    if display_name:
        first_name, _, last_name = display_name.strip().partition(' ')
        first_name = first_name[:256]
        last_name = last_name.strip()[:256]
        if (user.first_name, user.last_name) != (first_name, last_name):
            user.first_name = first_name
            user.last_name = last_name
            update_fields.extend(['first_name', 'last_name'])

    normalized_avatar = normalized_avatar_url(avatar_url)
    if normalized_avatar is not None and user.external_avatar_url != normalized_avatar:
        user.external_avatar_url = normalized_avatar
        update_fields.append('external_avatar_url')

    if update_fields:
        user.save(update_fields=update_fields)

    org = organization or user.active_organization or Organization.objects.first()
    if org is not None:
        org.add_user(user)
        if user.active_organization_id != org.id:
            user.active_organization = org
            user.save(update_fields=['active_organization'])
    return user
