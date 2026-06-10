from django.conf import settings
from django.db import models


class BridgeIdentity(models.Model):
    """Maps an OpenTrain control-plane user id to a runtime shadow user."""

    opentrain_user_id = models.CharField(max_length=128, unique=True)
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='open_label_bridge_identity',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'open_label_bridge_identity'


class BridgeConsumedNonce(models.Model):
    nonce_hash = models.CharField(max_length=64, unique=True)
    session_id = models.CharField(max_length=128)
    consumed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'open_label_bridge_consumed_nonce'


class BridgeProjectLink(models.Model):
    """Correlates a runtime project with the OpenTrain entities that provisioned it."""

    project = models.OneToOneField(
        'projects.Project',
        on_delete=models.CASCADE,
        related_name='open_label_bridge_link',
    )
    opentrain_assessment_id = models.CharField(max_length=128, null=True, blank=True)
    opentrain_assessment_version_id = models.CharField(max_length=128, null=True, blank=True)
    opentrain_project_id = models.CharField(max_length=128, null=True, blank=True)
    opentrain_project_version_id = models.CharField(max_length=128, null=True, blank=True)
    task_type = models.CharField(max_length=128, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'open_label_bridge_project_link'
