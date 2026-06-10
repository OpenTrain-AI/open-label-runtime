"""Verification for OpenTrain control-plane launch tokens.

Token format mirrors the control plane's runtime-bridge.ts: a base64url-encoded
stable-JSON payload, a dot, and a base64url HMAC-SHA256 signature of the encoded
payload string.
"""

import base64
import hashlib
import hmac
import json
import os
import time

VALID_ACTOR_ROLES = ('candidate', 'employer_review')


class BridgeTokenError(Exception):
    def __init__(self, reason):
        self.reason = reason
        super().__init__(reason)


def get_signing_secret():
    return (
        os.environ.get('OPEN_LABEL_SESSION_SIGNING_SECRET') or os.environ.get('OPEN_LABEL_BRIDGE_SIGNING_SECRET') or ''
    )


def _b64url_decode(value):
    return base64.urlsafe_b64decode(value + '=' * (-len(value) % 4))


def _b64url_encode(raw):
    return base64.urlsafe_b64encode(raw).rstrip(b'=').decode('ascii')


def stable_json(payload):
    return json.dumps(payload, sort_keys=True, separators=(',', ':'))


def sign_launch_payload(payload, secret=None):
    secret = secret if secret is not None else get_signing_secret()
    body = _b64url_encode(stable_json(payload).encode('utf-8'))
    signature = _b64url_encode(hmac.new(secret.encode('utf-8'), body.encode('ascii'), hashlib.sha256).digest())
    return f'{body}.{signature}'


def verify_launch_token(token):
    secret = get_signing_secret()
    if not secret:
        raise BridgeTokenError('missing_secret')
    if not token or token.count('.') != 1:
        raise BridgeTokenError('invalid_token')
    body, signature = token.split('.')
    if not body or not signature:
        raise BridgeTokenError('invalid_token')

    expected = _b64url_encode(hmac.new(secret.encode('utf-8'), body.encode('ascii'), hashlib.sha256).digest())
    if not hmac.compare_digest(signature, expected):
        raise BridgeTokenError('invalid_signature')

    try:
        payload = json.loads(_b64url_decode(body))
    except (ValueError, UnicodeDecodeError):
        raise BridgeTokenError('invalid_payload')
    if not isinstance(payload, dict):
        raise BridgeTokenError('invalid_payload')

    exp = payload.get('exp')
    if not isinstance(exp, (int, float)) or exp < time.time():
        raise BridgeTokenError('expired')

    for field in ('sessionId', 'nonce', 'actorUserId'):
        value = payload.get(field)
        if not isinstance(value, str) or not value:
            raise BridgeTokenError('invalid_payload')
    if payload.get('actorRole') not in VALID_ACTOR_ROLES:
        raise BridgeTokenError('invalid_payload')

    return payload
