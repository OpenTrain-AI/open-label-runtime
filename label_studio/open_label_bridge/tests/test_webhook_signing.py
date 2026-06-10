import hashlib
import hmac
import json

import pytest
import responses
from open_label_bridge.tests.utils import WEBHOOK_SECRET
from webhooks.models import Webhook
from webhooks.utils import run_webhook_sync

TARGET_URL = 'http://control-plane.test/api/webhooks/open-label'


@pytest.fixture
def webhook(org_with_project):
    organization, project, _ = org_with_project
    return Webhook.objects.create(
        organization=organization,
        project=project,
        url=TARGET_URL,
        headers={'x-open-label-secret': WEBHOOK_SECRET},
        send_payload=True,
        send_for_all_actions=True,
    )


@pytest.mark.django_db
@responses.activate
def test_outbound_webhook_is_signed(signing_env, webhook):
    responses.add(responses.POST, TARGET_URL, json={'ok': True}, status=200)

    run_webhook_sync(webhook, 'PROJECT_UPDATED', {'project': {'id': webhook.project_id}})

    assert len(responses.calls) == 1
    request = responses.calls[0].request
    body = request.body if isinstance(request.body, str) else request.body.decode('utf-8')

    payload = json.loads(body)
    assert payload['action'] == 'PROJECT_UPDATED'
    assert payload['project'] == {'id': webhook.project_id}

    expected = hmac.new(WEBHOOK_SECRET.encode('utf-8'), body.encode('utf-8'), hashlib.sha256).hexdigest()
    assert request.headers['x-open-label-signature'] == f'sha256={expected}'
    assert request.headers['x-open-label-secret'] == WEBHOOK_SECRET
    assert request.headers['Content-Type'] == 'application/json'


@pytest.mark.django_db
@responses.activate
def test_outbound_webhook_without_secret_has_no_signature(webhook, monkeypatch):
    monkeypatch.delenv('OPEN_LABEL_WEBHOOK_SECRET', raising=False)
    responses.add(responses.POST, TARGET_URL, json={'ok': True}, status=200)

    run_webhook_sync(webhook, 'PROJECT_UPDATED', {'project': {'id': webhook.project_id}})

    request = responses.calls[0].request
    assert 'x-open-label-signature' not in request.headers
