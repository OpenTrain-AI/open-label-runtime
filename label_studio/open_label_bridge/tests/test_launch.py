import pytest
import responses
from django.test import Client
from open_label_bridge.models import BridgeConsumedNonce, BridgeIdentity
from open_label_bridge.tests.utils import CONSUME_URL, launch_payload, make_token


def mock_consume(status=200):
    responses.add(responses.POST, CONSUME_URL, json={'ok': status < 400}, status=status)


@pytest.mark.django_db
@responses.activate
def test_candidate_launch_happy_path(signing_env, org_with_project):
    organization, project, _ = org_with_project
    mock_consume()
    token = make_token(launch_payload(project, actorUserId='ot-cand-1'))

    client = Client()
    response = client.get('/open-label/launch', {'session': token})

    assert response.status_code == 302
    assert response['Location'] == f'/projects/{project.id}/data?labeling=1'

    identity = BridgeIdentity.objects.get(opentrain_user_id='ot-cand-1')
    user = identity.user
    assert user.email == 'ol-ot-cand-1@runtime.opentrain.invalid'
    assert user.active_organization_id == organization.id
    assert organization.users.filter(id=user.id).exists()
    assert BridgeConsumedNonce.objects.filter(session_id='sess-1').exists()

    bridge = client.session.get('open_label_bridge')
    assert bridge['role'] == 'candidate'
    assert bridge['projectId'] == project.id


@pytest.mark.django_db
@responses.activate
def test_employer_review_landing(signing_env, org_with_project):
    _, project, _ = org_with_project
    mock_consume()
    token = make_token(launch_payload(project, actorRole='employer_review', actorUserId='ot-emp-1', nonce='nonce-emp'))

    response = Client().get('/open-label/launch', {'session': token})
    assert response.status_code == 302
    assert response['Location'] == f'/projects/{project.id}/data'


@pytest.mark.django_db
@responses.activate
def test_reviewer_landing_and_restrictions(signing_env, org_with_project):
    organization, project, owner = org_with_project
    from projects.models import Project

    other_project = Project.objects.create(
        title='Other Project', label_config='<View></View>', organization=organization, created_by=owner
    )
    mock_consume()
    token = make_token(launch_payload(project, actorRole='reviewer', actorUserId='ot-qa-1', nonce='nonce-reviewer'))

    client = Client()
    response = client.get('/open-label/launch', {'session': token})
    assert response.status_code == 302
    assert response['Location'] == f'/projects/{project.id}/data'

    bridge = client.session.get('open_label_bridge')
    assert bridge['role'] == 'reviewer'
    assert bridge['projectId'] == project.id

    assert client.get('/api/webhooks/').status_code == 403
    assert client.get(f'/api/projects/{project.id}/export').status_code == 403
    assert client.get(f'/api/projects/{other_project.id}/').status_code == 403


@pytest.mark.django_db
@responses.activate
def test_replay_rejected(signing_env, org_with_project):
    _, project, _ = org_with_project
    mock_consume()
    token = make_token(launch_payload(project, nonce='nonce-replay'))

    first = Client().get('/open-label/launch', {'session': token})
    assert first.status_code == 302

    second = Client().get('/open-label/launch', {'session': token})
    assert second.status_code == 403
    assert second['x-open-label-bridge-reason'] == 'replayed'
    assert b'Label Studio' not in second.content


@pytest.mark.django_db
@responses.activate
def test_control_plane_409_rejected(signing_env, org_with_project):
    _, project, _ = org_with_project
    mock_consume(status=409)
    token = make_token(launch_payload(project, nonce='nonce-409'))

    response = Client().get('/open-label/launch', {'session': token})
    assert response.status_code == 403
    assert response['x-open-label-bridge-reason'] == 'replayed'


@pytest.mark.django_db
def test_strict_mode_unconfigured_control_plane(signing_env, org_with_project, monkeypatch):
    monkeypatch.delenv('OPEN_LABEL_CONTROL_PLANE_BASE_URL', raising=False)
    _, project, _ = org_with_project
    token = make_token(launch_payload(project, nonce='nonce-strict'))

    response = Client().get('/open-label/launch', {'session': token})
    assert response.status_code == 403
    assert response['x-open-label-bridge-reason'] == 'control_plane_unconfigured'


@pytest.mark.django_db
@responses.activate
def test_non_strict_mode_allows_local_only(signing_env, org_with_project, monkeypatch):
    monkeypatch.delenv('OPEN_LABEL_CONTROL_PLANE_BASE_URL', raising=False)
    monkeypatch.setenv('OPEN_LABEL_BRIDGE_CONSUME_STRICT', '0')
    _, project, _ = org_with_project
    token = make_token(launch_payload(project, nonce='nonce-lenient'))

    response = Client().get('/open-label/launch', {'session': token})
    assert response.status_code == 302


@pytest.mark.django_db
@responses.activate
def test_middleware_catches_shipped_url_shape(signing_env, org_with_project):
    _, project, _ = org_with_project
    mock_consume()
    token = make_token(launch_payload(project, nonce='nonce-mw'))

    response = Client().get(
        f'/projects/{project.id}',
        {'session': token, 'downloadPolicy': 'block_source_assets'},
    )
    assert response.status_code == 302
    assert response['Location'] == f'/projects/{project.id}'


@pytest.mark.django_db
def test_invalid_token_denied_page(signing_env):
    response = Client().get('/open-label/launch', {'session': 'garbage'})
    assert response.status_code == 403
    assert response['x-open-label-bridge-reason'] == 'invalid_token'
    assert b'Return to OpenTrain' in response.content


@pytest.mark.django_db
@responses.activate
def test_candidate_blocked_surfaces(signing_env, org_with_project):
    organization, project, owner = org_with_project
    from projects.models import Project

    other_project = Project.objects.create(
        title='Other Project', label_config='<View></View>', organization=organization, created_by=owner
    )
    mock_consume()
    token = make_token(launch_payload(project, nonce='nonce-access'))

    client = Client()
    assert client.get('/open-label/launch', {'session': token}).status_code == 302

    assert client.get('/api/webhooks/').status_code == 403
    assert client.get('/api/organizations/').status_code == 403
    assert client.get(f'/api/projects/{project.id}/export').status_code == 403
    assert client.get(f'/api/projects/{other_project.id}/').status_code == 403
    assert client.patch(f'/api/projects/{project.id}/', data='{}', content_type='application/json').status_code == 403
