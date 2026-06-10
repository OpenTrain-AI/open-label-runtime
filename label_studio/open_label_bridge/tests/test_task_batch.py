import json

import pytest
from django.test import Client
from rest_framework.authtoken.models import Token
from tasks.models import Task


def auth_headers(user):
    token, _ = Token.objects.get_or_create(user=user)
    return {'HTTP_AUTHORIZATION': f'Token {token.key}'}


def post_tasks(user, project, payload):
    return Client().post(
        f'/open-label/bridge/projects/{project.id}/tasks',
        data=json.dumps(payload),
        content_type='application/json',
        **auth_headers(user),
    )


def batch_payload(*ids):
    return {
        'tasks': [
            {'openTrainTaskId': task_id, 'data': {'text': f'row for {task_id}', 'opentrain_task_id': task_id}}
            for task_id in ids
        ]
    }


@pytest.mark.django_db
def test_task_batch_creates_tasks_with_opentrain_ids(org_with_project):
    _, project, owner = org_with_project
    response = post_tasks(owner, project, batch_payload('ot-task-1', 'ot-task-2'))

    assert response.status_code == 201
    created = response.json()['created']
    assert [entry['openTrainTaskId'] for entry in created] == ['ot-task-1', 'ot-task-2']
    assert Task.objects.filter(project=project).count() == 2
    for entry in created:
        task = Task.objects.get(id=int(entry['runtimeTaskId']))
        assert task.project_id == project.id
        assert task.data['opentrain_task_id'] == entry['openTrainTaskId']
        assert task.data['text'] == f"row for {entry['openTrainTaskId']}"


@pytest.mark.django_db
def test_task_batch_is_idempotent_on_opentrain_task_id(org_with_project):
    _, project, owner = org_with_project
    first = post_tasks(owner, project, batch_payload('ot-task-1', 'ot-task-2'))
    assert first.status_code == 201
    first_ids = {entry['openTrainTaskId']: entry['runtimeTaskId'] for entry in first.json()['created']}

    second = post_tasks(owner, project, batch_payload('ot-task-1', 'ot-task-2', 'ot-task-3'))
    assert second.status_code == 201
    second_ids = {entry['openTrainTaskId']: entry['runtimeTaskId'] for entry in second.json()['created']}

    assert Task.objects.filter(project=project).count() == 3
    assert second_ids['ot-task-1'] == first_ids['ot-task-1']
    assert second_ids['ot-task-2'] == first_ids['ot-task-2']
    assert 'ot-task-3' in second_ids

    replay = post_tasks(owner, project, batch_payload('ot-task-1', 'ot-task-2', 'ot-task-3'))
    assert replay.status_code == 200
    assert Task.objects.filter(project=project).count() == 3
    assert {entry['openTrainTaskId']: entry['runtimeTaskId'] for entry in replay.json()['created']} == second_ids


@pytest.mark.django_db
def test_task_batch_server_side_opentrain_id_wins(org_with_project):
    _, project, owner = org_with_project
    response = post_tasks(
        owner,
        project,
        {'tasks': [{'openTrainTaskId': 'ot-real', 'data': {'opentrain_task_id': 'ot-spoofed', 'text': 'x'}}]},
    )
    assert response.status_code == 201
    task = Task.objects.get(project=project)
    assert task.data['opentrain_task_id'] == 'ot-real'


@pytest.mark.django_db
def test_task_batch_rejects_invalid_entries(org_with_project):
    _, project, owner = org_with_project
    assert post_tasks(owner, project, {'tasks': []}).status_code == 400
    assert post_tasks(owner, project, {'tasks': 'nope'}).status_code == 400
    assert post_tasks(owner, project, {'tasks': [{'data': {'text': 'x'}}]}).status_code == 400
    assert post_tasks(owner, project, {'tasks': [{'openTrainTaskId': 'ot-1', 'data': 'nope'}]}).status_code == 400
    duplicated = post_tasks(
        owner,
        project,
        {
            'tasks': [
                {'openTrainTaskId': 'ot-1', 'data': {'text': 'a'}},
                {'openTrainTaskId': 'ot-1', 'data': {'text': 'b'}},
            ]
        },
    )
    assert duplicated.status_code == 400
    assert Task.objects.filter(project=project).count() == 0


@pytest.mark.django_db
def test_task_batch_unknown_project_returns_404(org_with_project):
    _, project, owner = org_with_project
    response = Client().post(
        f'/open-label/bridge/projects/{project.id + 999}/tasks',
        data=json.dumps(batch_payload('ot-task-1')),
        content_type='application/json',
        **auth_headers(owner),
    )
    assert response.status_code == 404


@pytest.mark.django_db
def test_task_batch_requires_authentication(org_with_project):
    _, project, _ = org_with_project
    response = Client().post(
        f'/open-label/bridge/projects/{project.id}/tasks',
        data=json.dumps(batch_payload('ot-task-1')),
        content_type='application/json',
    )
    assert response.status_code == 401
