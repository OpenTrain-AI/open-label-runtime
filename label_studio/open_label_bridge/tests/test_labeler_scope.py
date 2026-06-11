import json

import pytest
import responses
from django.test import Client
from open_label_bridge.tests.utils import CONSUME_URL, launch_payload, make_token
from tasks.models import Task


def mock_consume(status=200):
    responses.add(responses.POST, CONSUME_URL, json={'ok': status < 400}, status=status)


def labeler_payload(project, **overrides):
    payload = launch_payload(
        project,
        actorRole='labeler',
        actorUserId=overrides.pop('actorUserId', 'ot-labeler-1'),
        **overrides,
    )
    payload['assessmentId'] = None
    payload['assessmentVersionId'] = None
    payload['attemptId'] = None
    payload.setdefault('assignmentId', 'assignment-1')
    payload.setdefault('projectId', 'ot-project-1')
    return payload


def make_tasks(project):
    in_scope = Task.objects.create(
        project=project, data={'text': 'in scope', 'opentrain_task_id': 'ot-task-1', 'opentrain_dataset_id': 'ds-1'}
    )
    out_of_scope = Task.objects.create(
        project=project, data={'text': 'out of scope', 'opentrain_task_id': 'ot-task-2', 'opentrain_dataset_id': 'ds-2'}
    )
    return in_scope, out_of_scope


@pytest.mark.django_db
@responses.activate
def test_labeler_launch_lands_in_label_stream(signing_env, org_with_project):
    organization, project, _ = org_with_project
    mock_consume()
    token = make_token(labeler_payload(project, nonce='nonce-labeler-1'))

    client = Client()
    response = client.get('/open-label/launch', {'session': token})

    assert response.status_code == 302
    assert response['Location'] == f'/projects/{project.id}/data?labeling=1'

    bridge = client.session.get('open_label_bridge')
    assert bridge['role'] == 'labeler'
    assert bridge['projectId'] == project.id
    assert bridge['assignmentId'] == 'assignment-1'
    assert bridge['scopeDatasetId'] is None
    assert bridge['scopeTaskIds'] is None


@pytest.mark.django_db
@responses.activate
def test_labeler_blocked_surfaces(signing_env, org_with_project):
    organization, project, owner = org_with_project
    from projects.models import Project

    other_project = Project.objects.create(
        title='Other Project', label_config='<View></View>', organization=organization, created_by=owner
    )
    mock_consume()
    token = make_token(labeler_payload(project, nonce='nonce-labeler-2'))

    client = Client()
    assert client.get('/open-label/launch', {'session': token}).status_code == 302

    assert client.get('/api/webhooks/').status_code == 403
    assert client.get('/api/organizations/').status_code == 403
    assert client.get(f'/api/projects/{project.id}/export').status_code == 403
    assert client.get(f'/api/projects/{other_project.id}/').status_code == 403
    assert client.patch(f'/api/projects/{project.id}/', data='{}', content_type='application/json').status_code == 403

    # The Data Manager needs the org-scoped user list to render annotators,
    # so reads pass while writes stay blocked.
    assert client.get('/api/users/').status_code == 200
    assert client.post('/api/users/', data='{}', content_type='application/json').status_code == 403


@pytest.mark.django_db
@responses.activate
def test_dataset_scope_filters_task_lists_and_next_task(signing_env, org_with_project):
    _, project, _ = org_with_project
    in_scope, out_of_scope = make_tasks(project)
    mock_consume()
    token = make_token(labeler_payload(project, nonce='nonce-labeler-3', scopeDatasetId='ds-1'))

    client = Client()
    assert client.get('/open-label/launch', {'session': token}).status_code == 302
    assert client.session['open_label_bridge']['scopeDatasetId'] == 'ds-1'

    listed = client.get('/api/tasks/', {'project': project.id})
    assert listed.status_code == 200
    listed_ids = [task['id'] for task in listed.json()['tasks']]
    assert listed_ids == [in_scope.id]

    next_task = client.get(f'/api/projects/{project.id}/next/')
    assert next_task.status_code == 200
    assert next_task.json()['id'] == in_scope.id

    assert client.get(f'/api/tasks/{in_scope.id}/').status_code == 200
    assert client.get(f'/api/tasks/{out_of_scope.id}/').status_code == 403


@pytest.mark.django_db
@responses.activate
def test_task_set_scope_restricts_to_listed_runtime_tasks(signing_env, org_with_project):
    _, project, _ = org_with_project
    in_scope, out_of_scope = make_tasks(project)
    mock_consume()
    token = make_token(
        labeler_payload(project, nonce='nonce-labeler-4', scopeRuntimeTaskIds=[str(in_scope.id)])
    )

    client = Client()
    assert client.get('/open-label/launch', {'session': token}).status_code == 302
    assert client.session['open_label_bridge']['scopeTaskIds'] == [in_scope.id]

    listed = client.get('/api/tasks/', {'project': project.id})
    assert listed.status_code == 200
    listed_ids = [task['id'] for task in listed.json()['tasks']]
    assert listed_ids == [in_scope.id]

    next_task = client.get(f'/api/projects/{project.id}/next/')
    assert next_task.status_code == 200
    assert next_task.json()['id'] == in_scope.id

    assert client.get(f'/api/tasks/{out_of_scope.id}/').status_code == 403
    denied_annotation = client.post(
        f'/api/tasks/{out_of_scope.id}/annotations/',
        data=json.dumps({'result': []}),
        content_type='application/json',
    )
    assert denied_annotation.status_code == 403


@pytest.mark.django_db
@responses.activate
def test_scope_blocks_out_of_scope_annotations(signing_env, org_with_project):
    _, project, _ = org_with_project
    in_scope, out_of_scope = make_tasks(project)
    mock_consume()
    token = make_token(labeler_payload(project, nonce='nonce-labeler-5', scopeDatasetId='ds-1'))

    client = Client()
    assert client.get('/open-label/launch', {'session': token}).status_code == 302

    created = client.post(
        f'/api/tasks/{in_scope.id}/annotations/',
        data=json.dumps({'result': []}),
        content_type='application/json',
    )
    assert created.status_code == 201
    annotation_id = created.json()['id']
    assert client.get(f'/api/annotations/{annotation_id}/').status_code == 200

    from tasks.models import Annotation

    out_annotation = Annotation.objects.create(task=out_of_scope, project=project, result=[])
    assert client.get(f'/api/annotations/{out_annotation.id}/').status_code == 403


@pytest.mark.django_db
@responses.activate
def test_unscoped_candidate_sessions_see_whole_project(signing_env, org_with_project):
    _, project, _ = org_with_project
    in_scope, out_of_scope = make_tasks(project)
    mock_consume()
    token = make_token(launch_payload(project, nonce='nonce-cand-scope'))

    client = Client()
    assert client.get('/open-label/launch', {'session': token}).status_code == 302

    listed = client.get('/api/tasks/', {'project': project.id})
    assert listed.status_code == 200
    listed_ids = {task['id'] for task in listed.json()['tasks']}
    assert listed_ids == {in_scope.id, out_of_scope.id}
