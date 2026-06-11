"""Move control-plane webhooks from per-project to organization level.

PROJECT_CREATED/PROJECT_DELETED are organization-only webhook actions, so
per-project webhooks never deliver them. Ensure each bridge tenant org has a
single org-level webhook and drop the legacy per-project ones.
"""

import os

from django.db import migrations


def _control_plane_url_and_headers():
    base = os.environ.get('OPEN_LABEL_CONTROL_PLANE_BASE_URL', '').strip().rstrip('/')
    if not base:
        return None, None
    headers = {}
    secret = os.environ.get('OPEN_LABEL_WEBHOOK_SECRET', '').strip()
    if secret:
        headers['x-open-label-secret'] = secret
    bypass = os.environ.get('OPEN_LABEL_CONTROL_PLANE_BYPASS_TOKEN', '').strip()
    if bypass:
        headers['x-vercel-protection-bypass'] = bypass
    return f'{base}/api/webhooks/open-label', headers


def forwards(apps, schema_editor):
    url, headers = _control_plane_url_and_headers()
    if not url:
        return

    Webhook = apps.get_model('webhooks', 'Webhook')
    BridgeOrganizationLink = apps.get_model('open_label_bridge', 'BridgeOrganizationLink')

    organization_ids = set(BridgeOrganizationLink.objects.values_list('organization_id', flat=True))
    organization_ids.update(
        Webhook.objects.filter(url=url, project__isnull=False).values_list('organization_id', flat=True)
    )
    for organization_id in organization_ids:
        if not Webhook.objects.filter(organization_id=organization_id, project__isnull=True, url=url).exists():
            Webhook.objects.create(
                organization_id=organization_id,
                project=None,
                url=url,
                headers=headers,
                send_payload=True,
                send_for_all_actions=True,
                is_active=True,
            )
    Webhook.objects.filter(url=url, project__isnull=False).delete()


class Migration(migrations.Migration):
    dependencies = [
        ('open_label_bridge', '0002_bridgeorganizationlink'),
        ('webhooks', '0004_auto_20221221_1101'),
    ]

    operations = [migrations.RunPython(forwards, migrations.RunPython.noop)]
