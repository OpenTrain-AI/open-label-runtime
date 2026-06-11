import pytest
from django.test import Client
from open_label_bridge.models import BridgeIdentity
from rest_framework.authtoken.models import Token
from tasks.models import Annotation, Task


def auth_headers(user):
    token, _ = Token.objects.get_or_create(user=user)
    return {'HTTP_AUTHORIZATION': f'Token {token.key}'}


def get_annotations(user, project_id, query=''):
    return Client().get(
        f'/open-label/bridge/projects/{project_id}/annotations{query}',
        **auth_headers(user),
    )


def make_task(project, opentrain_task_id):
    return Task.objects.create(
        project=project,
        data={'text': f'row for {opentrain_task_id}', 'opentrain_task_id': opentrain_task_id},
    )


@pytest.mark.django_db
def test_annotations_requires_authentication(org_with_project):
    _, project, _ = org_with_project
    response = Client().get(f'/open-label/bridge/projects/{project.id}/annotations')
    assert response.status_code == 401


@pytest.mark.django_db
def test_annotations_unknown_project_returns_404(org_with_project):
    _, _, owner = org_with_project
    response = get_annotations(owner, 999999)
    assert response.status_code == 404


@pytest.mark.django_db
def test_annotations_maps_bridge_identity_to_opentrain_user(org_with_project, django_user_model):
    _, project, owner = org_with_project
    annotator = django_user_model.objects.create_user(email='annotator@example.com', password='pass-1234')
    BridgeIdentity.objects.create(opentrain_user_id='ot-user-42', user=annotator)

    task = make_task(project, 'ot-task-1')
    Annotation.objects.create(
        task=task,
        project=project,
        completed_by=annotator,
        result=[{'value': {'choices': ['Positive']}}],
        lead_time=12.5,
    )

    response = get_annotations(owner, project.id)
    assert response.status_code == 200
    body = response.json()
    assert body['total'] == 1
    assert body['hasMore'] is False

    task_payload = body['tasks'][0]
    assert task_payload['runtimeTaskId'] == str(task.id)
    assert task_payload['openTrainTaskId'] == 'ot-task-1'

    annotation_payload = task_payload['annotations'][0]
    assert annotation_payload['result'] == [{'value': {'choices': ['Positive']}}]
    assert annotation_payload['completedByOpenTrainUserId'] == 'ot-user-42'
    assert annotation_payload['wasCancelled'] is False
    assert annotation_payload['leadTimeSeconds'] == 12.5
    assert annotation_payload['createdAt']
    assert annotation_payload['updatedAt']


@pytest.mark.django_db
def test_annotations_without_bridge_identity_reports_null_annotator(org_with_project, django_user_model):
    _, project, owner = org_with_project
    runtime_only = django_user_model.objects.create_user(email='runtime-only@example.com', password='pass-1234')

    task = make_task(project, 'ot-task-1')
    Annotation.objects.create(
        task=task,
        project=project,
        completed_by=runtime_only,
        result=[],
        was_cancelled=True,
    )

    response = get_annotations(owner, project.id)
    assert response.status_code == 200
    annotation_payload = response.json()['tasks'][0]['annotations'][0]
    assert annotation_payload['completedByOpenTrainUserId'] is None
    assert annotation_payload['wasCancelled'] is True


@pytest.mark.django_db
def test_annotations_pagination_orders_by_task_id(org_with_project):
    _, project, owner = org_with_project
    tasks = [make_task(project, f'ot-task-{index}') for index in range(3)]

    first_page = get_annotations(owner, project.id, '?page=1&pageSize=2')
    assert first_page.status_code == 200
    first_body = first_page.json()
    assert first_body['total'] == 3
    assert first_body['hasMore'] is True
    assert [entry['runtimeTaskId'] for entry in first_body['tasks']] == [str(tasks[0].id), str(tasks[1].id)]

    second_page = get_annotations(owner, project.id, '?page=2&pageSize=2')
    second_body = second_page.json()
    assert second_body['hasMore'] is False
    assert [entry['runtimeTaskId'] for entry in second_body['tasks']] == [str(tasks[2].id)]

    assert first_body['tasks'][0]['annotations'] == []


@pytest.mark.django_db
def test_annotations_rejects_invalid_pagination(org_with_project):
    _, project, owner = org_with_project
    assert get_annotations(owner, project.id, '?page=0').status_code == 400
    assert get_annotations(owner, project.id, '?pageSize=abc').status_code == 400
