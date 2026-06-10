"""Single-use nonce enforcement: local replay table plus control-plane consume callback."""

import hashlib
import hmac
import json
import logging
import os

import requests
from django.db import IntegrityError, transaction

from .models import BridgeConsumedNonce
from .tokens import get_signing_secret

logger = logging.getLogger(__name__)

CONSUME_TIMEOUT_SECONDS = 10


class BridgeConsumeError(Exception):
    def __init__(self, reason):
        self.reason = reason
        super().__init__(reason)


def hash_nonce(nonce):
    return hashlib.sha256(nonce.encode('utf-8')).hexdigest()


def _control_plane_base_url():
    base = os.environ.get('OPEN_LABEL_CONTROL_PLANE_BASE_URL', '').strip()
    return base.rstrip('/') or None


def _strict_mode():
    return os.environ.get('OPEN_LABEL_BRIDGE_CONSUME_STRICT', '1').strip().lower() not in ('0', 'false', 'no')


def consume_nonce(payload):
    nonce_hash = hash_nonce(payload['nonce'])
    try:
        with transaction.atomic():
            BridgeConsumedNonce.objects.create(nonce_hash=nonce_hash, session_id=payload['sessionId'])
    except IntegrityError:
        raise BridgeConsumeError('replayed')

    base_url = _control_plane_base_url()
    if not base_url:
        if _strict_mode():
            raise BridgeConsumeError('control_plane_unconfigured')
        logger.warning('open_label_bridge: control plane base URL missing; local-only nonce consume')
        return

    body = json.dumps({'sessionId': payload['sessionId'], 'nonceHash': nonce_hash}, separators=(',', ':'))
    signature = hmac.new(get_signing_secret().encode('utf-8'), body.encode('utf-8'), hashlib.sha256).hexdigest()
    try:
        response = requests.post(
            f'{base_url}/api/open-label/runtime-sessions/consume',
            data=body,
            headers={
                'content-type': 'application/json',
                'x-open-label-signature': f'sha256={signature}',
            },
            timeout=CONSUME_TIMEOUT_SECONDS,
        )
    except requests.RequestException as exc:
        logger.error('open_label_bridge: control plane consume request failed: %s', exc)
        if _strict_mode():
            raise BridgeConsumeError('control_plane_unreachable')
        return

    if response.status_code == 409:
        raise BridgeConsumeError('replayed')
    if response.status_code >= 400:
        raise BridgeConsumeError(f'control_plane_{response.status_code}')
