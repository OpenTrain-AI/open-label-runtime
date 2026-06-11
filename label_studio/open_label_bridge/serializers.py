"""Webhook payload serializers that enrich runtime events with OpenTrain linkage."""

from rest_framework import serializers
from webhooks.serializers_for_hooks import ProjectWebhookSerializer

from .models import BridgeProjectLink


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
