from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('open_label_bridge', '0003_org_level_control_plane_webhooks'),
    ]

    operations = [
        migrations.AddField(
            model_name='bridgeprojectlink',
            name='linked_job_id',
            field=models.CharField(blank=True, max_length=128, null=True),
        ),
        migrations.AddField(
            model_name='bridgeprojectlink',
            name='linked_job_title',
            field=models.CharField(blank=True, max_length=512, null=True),
        ),
        migrations.AddField(
            model_name='bridgeprojectlink',
            name='linked_job_mode',
            field=models.CharField(blank=True, max_length=32, null=True),
        ),
    ]
