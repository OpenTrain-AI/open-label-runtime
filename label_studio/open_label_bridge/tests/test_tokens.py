import time

import pytest
from open_label_bridge.tests.utils import launch_payload, make_token
from open_label_bridge.tokens import BridgeTokenError, sign_launch_payload, verify_launch_token


def test_roundtrip(signing_env):
    payload = launch_payload(None, runtimeProjectId='12')
    token = make_token(payload)
    assert verify_launch_token(token) == payload


def test_tampered_signature_rejected(signing_env):
    token = make_token(launch_payload(None))
    body, signature = token.split('.')
    tampered = f'{body}.{signature[:-2]}aa'
    with pytest.raises(BridgeTokenError) as exc:
        verify_launch_token(tampered)
    assert exc.value.reason == 'invalid_signature'


def test_wrong_secret_rejected(signing_env):
    token = sign_launch_payload(launch_payload(None), 'some-other-secret')
    with pytest.raises(BridgeTokenError) as exc:
        verify_launch_token(token)
    assert exc.value.reason == 'invalid_signature'


def test_expired_rejected(signing_env):
    token = make_token(launch_payload(None, exp=int(time.time()) - 5))
    with pytest.raises(BridgeTokenError) as exc:
        verify_launch_token(token)
    assert exc.value.reason == 'expired'


def test_missing_secret(monkeypatch):
    monkeypatch.delenv('OPEN_LABEL_SESSION_SIGNING_SECRET', raising=False)
    monkeypatch.delenv('OPEN_LABEL_BRIDGE_SIGNING_SECRET', raising=False)
    with pytest.raises(BridgeTokenError) as exc:
        verify_launch_token('a.b')
    assert exc.value.reason == 'missing_secret'


def test_malformed_token(signing_env):
    for token in ('', 'no-dot', 'a.b.c'):
        with pytest.raises(BridgeTokenError) as exc:
            verify_launch_token(token)
        assert exc.value.reason == 'invalid_token'


@pytest.mark.parametrize('field', ['sessionId', 'nonce', 'actorUserId'])
def test_missing_required_field(signing_env, field):
    payload = launch_payload(None)
    payload[field] = ''
    with pytest.raises(BridgeTokenError) as exc:
        verify_launch_token(make_token(payload))
    assert exc.value.reason == 'invalid_payload'


def test_reviewer_role_accepted(signing_env):
    payload = launch_payload(None, actorRole='reviewer')
    assert verify_launch_token(make_token(payload)) == payload


def test_invalid_role(signing_env):
    payload = launch_payload(None, actorRole='admin')
    with pytest.raises(BridgeTokenError) as exc:
        verify_launch_token(make_token(payload))
    assert exc.value.reason == 'invalid_payload'
