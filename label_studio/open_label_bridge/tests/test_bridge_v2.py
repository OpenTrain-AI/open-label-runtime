"""Bridge v2: project update/link endpoints, workspace launches, embed mode headers."""

import json

import pytest
import responses
from django.conf import settings
from django.test import Client
from open_label_bridge.models import BridgeIdentity, BridgeOrganizationLink, BridgeProjectLink
from open_label_bridge.serializers import OpenLabelProjectWebhookSerializer
from open_label_bridge.tests.utils import CONSUME_URL, launch_payload, make_token
from projects.models import Project
from rest_framework.authtoken.models import Token


def auth_headers(user):
    token, _ = Token.objects.get_or_create(user=user)
    return {'HTTP_AUTHORIZATION': f'Token {token.key}'}


def patch_project(user, project_id, payload):
    return Client().patch(
        f'/open-label/bridge/projects/{project_id}',
        data=json.dumps(payload),
        content_type='application/json',
        **auth_headers(user),
    )


def post_link(user, project_id, payload):
    return Client().post(
        f'/open-label/bridge/projects/{project_id}/link',
        data=json.dumps(payload),
        content_type='application/json',
        **auth_headers(user),
    )


@pytest.mark.django_db
def test_project_update_renames_title_and_description(org_with_project):
    _, project, owner = org_with_project
    response = patch_project(owner, project.id, {'title': 'Renamed From OpenTrain', 'description': 'New details'})
    assert response.status_code == 200
    project.refresh_from_db()
    assert project.title == 'Renamed From OpenTrain'
    assert project.description == 'New details'


@pytest.mark.django_db
def test_project_update_truncates_long_title(org_with_project):
    _, project, owner = org_with_project
    title_max_length = Project._meta.get_field('title').max_length
    response = patch_project(owner, project.id, {'title': 'x' * (title_max_length + 50)})
    assert response.status_code == 200
    project.refresh_from_db()
    assert len(project.title) == title_max_length


@pytest.mark.django_db
def test_project_update_validation(org_with_project):
    _, project, owner = org_with_project
    assert patch_project(owner, project.id, {}).status_code == 400
    assert patch_project(owner, 999999, {'title': 'x'}).status_code == 404
    unauthenticated = Client().patch(
        f'/open-label/bridge/projects/{project.id}',
        data=json.dumps({'title': 'x'}),
        content_type='application/json',
    )
    assert unauthenticated.status_code == 401


@pytest.mark.django_db
def test_project_link_creates_and_updates(org_with_project):
    _, project, owner = org_with_project
    response = post_link(owner, project.id, {'projectId': 'olp-wizard-1', 'taskType': 'custom'})
    assert response.status_code == 201
    link = BridgeProjectLink.objects.get(project=project)
    assert link.opentrain_project_id == 'olp-wizard-1'
    assert link.task_type == 'custom'

    replay = post_link(owner, project.id, {'projectId': 'olp-wizard-1', 'projectVersionId': 'olpv-wizard-1'})
    assert replay.status_code == 200
    link.refresh_from_db()
    assert link.opentrain_project_version_id == 'olpv-wizard-1'
    assert BridgeProjectLink.objects.filter(project=project).count() == 1

    assert post_link(owner, 999999, {'projectId': 'x'}).status_code == 404


@pytest.mark.django_db
@responses.activate
def test_workspace_launch_lands_in_tenant_org(signing_env, org_with_project):
    _, _, owner = org_with_project
    responses.add(responses.POST, CONSUME_URL, json={'ok': True}, status=200)
    Client().post(
        '/open-label/bridge/organizations',
        data=json.dumps({'openTrainOrganizationId': 'ot-org-ws', 'title': 'Workspace Tenant'}),
        content_type='application/json',
        **auth_headers(owner),
    )
    link = BridgeOrganizationLink.objects.get(opentrain_organization_id='ot-org-ws')

    token = make_token(
        launch_payload(
            None,
            actorRole='employer_review',
            actorUserId='ot-emp-ws',
            nonce='nonce-ws',
            openTrainOrganizationId='ot-org-ws',
        )
    )
    response = Client().get('/open-label/launch', {'session': token})
    assert response.status_code == 302
    assert response['Location'] == '/projects/'

    identity = BridgeIdentity.objects.get(opentrain_user_id='ot-emp-ws')
    assert identity.user.active_organization_id == link.organization_id


@pytest.mark.django_db
@responses.activate
def test_embed_params_survive_launch_redirect(signing_env, org_with_project):
    _, project, _ = org_with_project
    responses.add(responses.POST, CONSUME_URL, json={'ok': True}, status=200)
    token = make_token(launch_payload(project, actorRole='employer_review', nonce='nonce-embed'))

    response = Client().get(
        '/projects/',
        {'session': token, 'embed': '1', 'create': '1', 'embedOrigin': 'https://app.opentrain.test'},
    )
    assert response.status_code == 302
    location = response['Location']
    assert 'session=' not in location
    assert 'embed=1' in location
    assert 'create=1' in location
    assert 'embedOrigin=' in location


@pytest.mark.django_db
def test_frame_ancestors_header(org_with_project, monkeypatch):
    monkeypatch.setenv('OPEN_LABEL_FRAME_ANCESTORS', "'self' https://app.opentrain.test")
    client = Client()
    client.force_login(org_with_project[2])
    response = client.get('/projects/')
    csp = response.headers.get('Content-Security-Policy', '')
    assert "frame-ancestors 'self' https://app.opentrain.test" in csp
    assert 'X-Frame-Options' not in response.headers


@pytest.mark.django_db
def test_frame_ancestors_header_absent_without_env(org_with_project, monkeypatch):
    monkeypatch.delenv('OPEN_LABEL_FRAME_ANCESTORS', raising=False)
    client = Client()
    client.force_login(org_with_project[2])
    response = client.get('/projects/')
    assert 'frame-ancestors' not in response.headers.get('Content-Security-Policy', '')


@pytest.mark.django_db
def test_project_webhook_serializer_includes_opentrain_linkage(org_with_project):
    _, project, _ = org_with_project
    assert settings.WEBHOOK_SERIALIZERS['project'] == (
        'open_label_bridge.serializers.OpenLabelProjectWebhookSerializer'
    )

    data = OpenLabelProjectWebhookSerializer(instance=project).data
    assert data['opentrain'] is None

    BridgeProjectLink.objects.create(project=project, opentrain_project_id='olp-77', task_type='image_bbox')
    data = OpenLabelProjectWebhookSerializer(instance=project).data
    assert data['opentrain']['projectId'] == 'olp-77'
    assert data['opentrain']['taskType'] == 'image_bbox'
    assert data['title'] == project.title
    assert data['is_draft'] is False
