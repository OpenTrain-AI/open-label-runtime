import time

from open_label_bridge.tokens import sign_launch_payload

SIGNING_SECRET = 'test-signing-secret'
CONTROL_PLANE_BASE = 'http://control-plane.test'
WEBHOOK_SECRET = 'test-webhook-secret'
CONSUME_URL = f'{CONTROL_PLANE_BASE}/api/open-label/runtime-sessions/consume'


def launch_payload(project, **overrides):
    payload = {
        'sessionId': overrides.pop('sessionId', 'sess-1'),
        'nonce': overrides.pop('nonce', 'nonce-1'),
        'assessmentId': 'assess-1',
        'assessmentVersionId': 'assess-v1',
        'attemptId': 'attempt-1',
        'actorUserId': overrides.pop('actorUserId', 'ot-user-1'),
        'actorRole': overrides.pop('actorRole', 'candidate'),
        'runtimeProjectId': str(project.id) if project else None,
        'exp': overrides.pop('exp', int(time.time()) + 600),
    }
    payload.update(overrides)
    return payload


def make_token(payload, secret=SIGNING_SECRET):
    return sign_launch_payload(payload, secret)
