"""Webhook payload serializers that enrich runtime events with OpenTrain linkage."""

from rest_framework import serializers
from webhooks.serializers_for_hooks import AnnotationWebhookSerializer, ProjectWebhookSerializer

from .models import BridgeIdentity, BridgeProjectLink


class OpenLabelProjectWebhookSerializer(ProjectWebhookSerializer):
    opentrain = serializers.SerializerMethodField()

    class Meta(ProjectWebhookSerializer.Meta):
        pass

    def get_opentrain(self, instance):
        link = BridgeProjectLink.objects.filter(project_id=instance.id).first()
        if link is None:
            return None
        return {
            'assessmentId': link.opentrain_assessment_id,
            'assessmentVersionId': link.opentrain_assessment_version_id,
            'projectId': link.opentrain_project_id,
            'projectVersionId': link.opentrain_project_version_id,
            'taskType': link.task_type,
        }


class OpenLabelAnnotationWebhookSerializer(AnnotationWebhookSerializer):
    """Reports the annotator as an OpenTrain user id so the control-plane work
    ledger can attribute time/labels without learning runtime identities."""

    completed_by_opentrain_user_id = serializers.SerializerMethodField()

    class Meta(AnnotationWebhookSerializer.Meta):
        pass

    def get_completed_by_opentrain_user_id(self, instance):
        if instance.completed_by_id is None:
            return None
        identity = BridgeIdentity.objects.filter(user_id=instance.completed_by_id).first()
        return identity.opentrain_user_id if identity else None
