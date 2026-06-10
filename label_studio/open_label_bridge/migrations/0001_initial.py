import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('projects', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='BridgeConsumedNonce',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nonce_hash', models.CharField(max_length=64, unique=True)),
                ('session_id', models.CharField(max_length=128)),
                ('consumed_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'db_table': 'open_label_bridge_consumed_nonce',
            },
        ),
        migrations.CreateModel(
            name='BridgeIdentity',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('opentrain_user_id', models.CharField(max_length=128, unique=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                (
                    'user',
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='open_label_bridge_identity',
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                'db_table': 'open_label_bridge_identity',
            },
        ),
        migrations.CreateModel(
            name='BridgeProjectLink',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('opentrain_assessment_id', models.CharField(blank=True, max_length=128, null=True)),
                ('opentrain_assessment_version_id', models.CharField(blank=True, max_length=128, null=True)),
                ('opentrain_project_id', models.CharField(blank=True, max_length=128, null=True)),
                ('opentrain_project_version_id', models.CharField(blank=True, max_length=128, null=True)),
                ('task_type', models.CharField(blank=True, max_length=128, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                (
                    'project',
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='open_label_bridge_link',
                        to='projects.project',
                    ),
                ),
            ],
            options={
                'db_table': 'open_label_bridge_project_link',
            },
        ),
    ]
