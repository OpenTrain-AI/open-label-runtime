"""Full-app shell (F3): project purpose field, bridge webhook lockout, and the
whitelabel flag that suppresses upstream Label Studio doc/branding links."""

import json

import pytest
import responses
from django.test import Client
from open_label_bridge.serializers import OpenLabelProjectWebhookSerializer
from open_label_bridge.tests.utils import CONSUME_URL, launch_payload, make_token
from projects.models import Project
from rest_framework.authtoken.models import Token

PROVISION_PATH = '/open-label/bridge/projects'

PROVISION_PAYLOAD = {
    'assessmentId': 'assess-p1',
    'assessmentVersionId': 'assess-vp1',
    'projectId': 'olp-p1',
    'projectVersionId': 'olpv-p1',
    'taskType': 'image_bbox',
    'labelStudioConfig': (
        '<View><Image name="img" value="$image"/>'
        '<RectangleLabels name="label" toName="img"><Label value="Car"/></RectangleLabels></View>'
    ),
}


def auth_headers(user):
    token, _ = Token.objects.get_or_create(user=user)
    return {'HTTP_AUTHORIZATION': f'Token {token.key}'}


def launch_bridge_client(project, **overrides):
    client = Client()
    token = make_token(launch_payload(project, **overrides))
    response = client.get('/open-label/launch', {'session': token})
    assert response.status_code == 302
    return client


def patch_project(user, project, body):
    return Client().patch(
        f'/api/projects/{project.id}/', data=json.dumps(body), content_type='application/json', **auth_headers(user)
    )


@pytest.mark.django_db
def test_project_purpose_patch_and_read(org_with_project):
    _, project, owner = org_with_project

    response = patch_project(owner, project, {'purpose': 'screening'})
    assert response.status_code == 200
    assert response.json()['purpose'] == 'screening'
    project.refresh_from_db()
    assert project.purpose == 'screening'

    response = patch_project(owner, project, {'purpose': 'production'})
    assert response.status_code == 200
    project.refresh_from_db()
    assert project.purpose == 'production'

    detail = Client().get(f'/api/projects/{project.id}/', **auth_headers(owner))
    assert detail.status_code == 200
    assert detail.json()['purpose'] == 'production'


@pytest.mark.django_db
def test_project_purpose_rejects_unknown_value(org_with_project):
    _, project, owner = org_with_project
    response = patch_project(owner, project, {'purpose': 'bogus'})
    assert response.status_code == 400
    project.refresh_from_db()
    assert project.purpose is None


@pytest.mark.django_db
def test_project_webhook_payload_includes_purpose(org_with_project):
    _, project, _ = org_with_project
    project.purpose = 'screening'
    project.save(update_fields=['purpose'])

    data = OpenLabelProjectWebhookSerializer(instance=project).data
    assert data['purpose'] == 'screening'


@pytest.mark.django_db
def test_provision_accepts_and_normalizes_purpose(signing_env, org_with_project):
    _, _, owner = org_with_project
    payload = dict(PROVISION_PAYLOAD, purpose='SCREENING')
    response = Client().post(
        PROVISION_PATH, data=json.dumps(payload), content_type='application/json', **auth_headers(owner)
    )
    assert response.status_code == 201
    project = Project.objects.get(id=int(response.json()['runtimeProjectId']))
    assert project.purpose == 'screening'


@pytest.mark.django_db
def test_provision_rejects_invalid_purpose(signing_env, org_with_project):
    _, _, owner = org_with_project
    payload = dict(PROVISION_PAYLOAD, projectId='olp-p2', purpose='bogus')
    response = Client().post(
        PROVISION_PATH, data=json.dumps(payload), content_type='application/json', **auth_headers(owner)
    )
    assert response.status_code == 400
    assert 'purpose' in response.json()['detail']


@pytest.mark.django_db
@responses.activate
def test_bridge_session_cannot_touch_webhooks(signing_env, org_with_project):
    _, project, owner = org_with_project
    responses.add(responses.POST, CONSUME_URL, json={'ok': True}, status=200)
    client = launch_bridge_client(project, actorRole='employer_review', nonce='nonce-webhooks')

    assert client.get('/api/webhooks/').status_code == 403
    create = client.post(
        '/api/webhooks/', data=json.dumps({'url': 'https://example.com/hook'}), content_type='application/json'
    )
    assert create.status_code == 403

    # Token-authenticated (non-bridge) sessions keep webhook access.
    native = Client().get('/api/webhooks/', **auth_headers(owner))
    assert native.status_code == 200


@pytest.mark.django_db
@responses.activate
def test_whitelabel_flag_present_in_rendered_pages(signing_env, org_with_project):
    _, project, _ = org_with_project
    responses.add(responses.POST, CONSUME_URL, json={'ok': True}, status=200)
    client = launch_bridge_client(project, actorRole='employer_review', nonce='nonce-whitelabel')

    page = client.get('/projects/')
    assert page.status_code == 200
    assert b'whitelabel_is_active: true' in page.content

    login_page = Client().get('/user/login/')
    assert login_page.status_code == 200
    assert b'whitelabel_is_active' in login_page.content
