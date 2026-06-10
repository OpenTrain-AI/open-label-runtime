import json

import pytest
from django.test import Client
from open_label_bridge.models import BridgeProjectLink
from open_label_bridge.tests.utils import CONTROL_PLANE_BASE, WEBHOOK_SECRET
from projects.models import Project
from rest_framework.authtoken.models import Token
from webhooks.models import Webhook

PROVISION_PATH = '/open-label/bridge/projects'

CONTROL_PLANE_PAYLOAD = {
    'assessmentId': 'assess-9',
    'assessmentVersionId': 'assess-v9',
    'projectId': 'olp-9',
    'projectVersionId': 'olpv-9',
    'taskType': 'image_bbox',
    'labelStudioConfig': (
        '<View><Image name="img" value="$image"/>'
        '<RectangleLabels name="label" toName="img"><Label value="Car"/></RectangleLabels></View>'
    ),
    'instructions': 'Draw boxes around cars.',
}


def auth_headers(user):
    token, _ = Token.objects.get_or_create(user=user)
    return {'HTTP_AUTHORIZATION': f'Token {token.key}'}


def post_provision(user, payload):
    return Client().post(
        PROVISION_PATH, data=json.dumps(payload), content_type='application/json', **auth_headers(user)
    )


@pytest.mark.django_db
def test_provision_creates_project_link_and_webhook(signing_env, org_with_project):
    organization, _, owner = org_with_project
    response = post_provision(owner, CONTROL_PLANE_PAYLOAD)

    assert response.status_code == 201
    data = response.json()
    project = Project.objects.get(id=int(data['runtimeProjectId']))
    assert data['runtimeProjectUrl'].endswith(f'/projects/{project.id}')
    assert project.organization_id == organization.id
    assert 'RectangleLabels' in project.label_config
    assert project.expert_instruction == 'Draw boxes around cars.'
    assert 'image_bbox' in project.title
    assert 'olp-9' in project.title

    link = BridgeProjectLink.objects.get(project=project)
    assert link.opentrain_project_id == 'olp-9'
    assert link.opentrain_assessment_id == 'assess-9'
    assert link.task_type == 'image_bbox'

    webhook = Webhook.objects.get(project=project)
    assert webhook.url == f'{CONTROL_PLANE_BASE}/api/webhooks/open-label'
    assert webhook.headers == {'x-open-label-secret': WEBHOOK_SECRET}
    assert webhook.send_payload is True
    assert webhook.send_for_all_actions is True


@pytest.mark.django_db
def test_provision_truncates_title_to_model_limit(signing_env, org_with_project):
    _, _, owner = org_with_project
    payload = dict(
        CONTROL_PLANE_PAYLOAD,
        projectId='cmnlte3u0003f04l5qbw60077-very-long-control-plane-identifier',
        taskType='image_classification',
    )
    response = post_provision(owner, payload)
    assert response.status_code == 201
    project = Project.objects.get(id=int(response.json()['runtimeProjectId']))
    title_max_length = Project._meta.get_field('title').max_length
    assert len(project.title) <= title_max_length
    assert project.title.startswith('Open Label')


@pytest.mark.django_db
def test_provision_accepts_nested_config_dict(signing_env, org_with_project):
    _, _, owner = org_with_project
    payload = dict(CONTROL_PLANE_PAYLOAD, labelStudioConfig={'xml': CONTROL_PLANE_PAYLOAD['labelStudioConfig']})
    response = post_provision(owner, payload)
    assert response.status_code == 201
    project = Project.objects.get(id=int(response.json()['runtimeProjectId']))
    assert 'RectangleLabels' in project.label_config


@pytest.mark.django_db
def test_provision_invalid_config_rejected(signing_env, org_with_project):
    _, _, owner = org_with_project
    payload = dict(CONTROL_PLANE_PAYLOAD, labelStudioConfig='<View><Bogus broken')
    response = post_provision(owner, payload)
    assert response.status_code == 400
    assert 'Invalid project configuration' in response.json()['detail']


@pytest.mark.django_db
def test_provision_without_webhook_base_skips_webhook(org_with_project, monkeypatch):
    monkeypatch.delenv('OPEN_LABEL_CONTROL_PLANE_BASE_URL', raising=False)
    _, _, owner = org_with_project
    response = post_provision(owner, CONTROL_PLANE_PAYLOAD)
    assert response.status_code == 201
    project_id = int(response.json()['runtimeProjectId'])
    assert not Webhook.objects.filter(project_id=project_id).exists()


@pytest.mark.django_db
def test_provision_requires_authentication(signing_env, org_with_project):
    response = Client().post(PROVISION_PATH, data=json.dumps(CONTROL_PLANE_PAYLOAD), content_type='application/json')
    assert response.status_code == 401
