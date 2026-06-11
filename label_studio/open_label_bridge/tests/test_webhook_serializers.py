import pytest
from open_label_bridge.models import BridgeIdentity
from open_label_bridge.serializers import OpenLabelAnnotationWebhookSerializer
from tasks.models import Annotation, Task


@pytest.mark.django_db
def test_annotation_webhook_reports_opentrain_user(org_with_project, django_user_model):
    _, project, _ = org_with_project
    annotator = django_user_model.objects.create_user(email='hook-annotator@example.com', password='pass-1234')
    BridgeIdentity.objects.create(opentrain_user_id='ot-user-7', user=annotator)

    task = Task.objects.create(project=project, data={'text': 'row'})
    annotation = Annotation.objects.create(task=task, project=project, completed_by=annotator, result=[])

    data = OpenLabelAnnotationWebhookSerializer(instance=annotation).data
    assert data['completed_by_opentrain_user_id'] == 'ot-user-7'
    assert data['completed_by'] == annotator.id


@pytest.mark.django_db
def test_annotation_webhook_without_identity_reports_null(org_with_project, django_user_model):
    _, project, _ = org_with_project
    runtime_only = django_user_model.objects.create_user(email='hook-runtime@example.com', password='pass-1234')

    task = Task.objects.create(project=project, data={'text': 'row'})
    annotation = Annotation.objects.create(task=task, project=project, completed_by=runtime_only, result=[])

    data = OpenLabelAnnotationWebhookSerializer(instance=annotation).data
    assert data['completed_by_opentrain_user_id'] is None
