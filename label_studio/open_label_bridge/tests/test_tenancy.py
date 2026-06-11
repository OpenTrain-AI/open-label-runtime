import json
import time

import pytest
from django.conf import settings
from django.test import Client
from open_label_bridge.models import BridgeOrganizationLink
from organizations.models import Organization, OrganizationMember
from projects.models import Project
from rest_framework.authtoken.models import Token
from tasks.models import Task
from webhooks.models import Webhook


def auth_headers(user):
    token, _ = Token.objects.get_or_create(user=user)
    return {'HTTP_AUTHORIZATION': f'Token {token.key}'}


def stamp_session_login(client, extra=None):
    # InactivitySessionTimeoutMiddleWare logs out sessions without this stamp.
    # With the signed_cookies backend, session.save() does not refresh the test
    # client's cookie, so re-sync it manually.
    session = client.session
    session['last_login'] = time.time()
    for key, value in (extra or {}).items():
        session[key] = value
    session.save()
    client.cookies[settings.SESSION_COOKIE_NAME] = session.session_key


def post_json(user, path, payload):
    return Client().post(path, data=json.dumps(payload), content_type='application/json', **auth_headers(user))


def create_org(user, opentrain_org_id, title=None):
    payload = {'openTrainOrganizationId': opentrain_org_id}
    if title:
        payload['title'] = title
    return post_json(user, '/open-label/bridge/organizations', payload)


@pytest.mark.django_db
def test_organization_create_is_idempotent(org_with_project):
    _, _, owner = org_with_project
    first = create_org(owner, 'ot-org-1', title='Acme Labeling')
    assert first.status_code == 201
    runtime_org_id = first.json()['runtimeOrganizationId']

    organization = Organization.objects.get(id=int(runtime_org_id))
    assert organization.title == 'Acme Labeling'
    link = BridgeOrganizationLink.objects.get(opentrain_organization_id='ot-org-1')
    assert link.organization_id == organization.id
    shadow_owner = organization.created_by
    assert shadow_owner is not None
    assert shadow_owner.email.startswith('ol-org-ot-org-1@')
    assert shadow_owner.active_organization_id == organization.id
    assert OrganizationMember.objects.filter(user=shadow_owner, organization=organization).exists()

    replay = create_org(owner, 'ot-org-1', title='Different Title')
    assert replay.status_code == 200
    assert replay.json()['runtimeOrganizationId'] == runtime_org_id
    assert Organization.objects.filter(title__startswith='Acme').count() == 1


@pytest.mark.django_db
def test_organization_create_rejects_missing_id(org_with_project):
    _, _, owner = org_with_project
    assert post_json(owner, '/open-label/bridge/organizations', {}).status_code == 400
    unauthenticated = Client().post(
        '/open-label/bridge/organizations',
        data=json.dumps({'openTrainOrganizationId': 'ot-org-x'}),
        content_type='application/json',
    )
    assert unauthenticated.status_code == 401


@pytest.mark.django_db
def test_project_create_lands_in_tenant_organization(org_with_project, signing_env):
    default_org, _, owner = org_with_project
    response = post_json(
        owner,
        '/open-label/bridge/projects',
        {
            'projectId': 'ot-project-9',
            'openTrainOrganizationId': 'ot-org-2',
            'labelStudioConfig': '<View><Text name="t" value="$text"/><Choices name="c" toName="t"><Choice value="A"/></Choices></View>',
        },
    )
    assert response.status_code == 201
    project = Project.objects.get(id=int(response.json()['runtimeProjectId']))
    link = BridgeOrganizationLink.objects.get(opentrain_organization_id='ot-org-2')
    assert project.organization_id == link.organization_id
    assert project.organization_id != default_org.id
    assert project.created_by_id == link.organization.created_by_id
    webhook = Webhook.objects.get(organization_id=link.organization_id, project__isnull=True)
    assert webhook.send_for_all_actions is True


@pytest.mark.django_db
def test_project_create_without_org_keeps_legacy_behavior(org_with_project):
    default_org, _, owner = org_with_project
    response = post_json(owner, '/open-label/bridge/projects', {'projectId': 'ot-project-legacy'})
    assert response.status_code == 201
    project = Project.objects.get(id=int(response.json()['runtimeProjectId']))
    assert project.organization_id == default_org.id


@pytest.mark.django_db
def test_project_move_endpoint_moves_project_and_webhooks(org_with_project, signing_env):
    default_org, project, owner = org_with_project
    Webhook.objects.create(organization=default_org, project=project, url='https://example.com/hook')

    response = post_json(
        owner,
        f'/open-label/bridge/projects/{project.id}/organization',
        {'openTrainOrganizationId': 'ot-org-3'},
    )
    assert response.status_code == 200
    body = response.json()
    assert body['moved'] is True
    link = BridgeOrganizationLink.objects.get(opentrain_organization_id='ot-org-3')
    project.refresh_from_db()
    assert project.organization_id == link.organization_id
    assert project.created_by_id == link.organization.created_by_id
    assert Webhook.objects.get(project=project).organization_id == link.organization_id

    replay = post_json(
        owner,
        f'/open-label/bridge/projects/{project.id}/organization',
        {'openTrainOrganizationId': 'ot-org-3'},
    )
    assert replay.status_code == 200
    assert replay.json()['moved'] is False

    missing = post_json(owner, '/open-label/bridge/projects/999999/organization', {'openTrainOrganizationId': 'x'})
    assert missing.status_code == 404
    no_org = post_json(owner, f'/open-label/bridge/projects/{project.id}/organization', {})
    assert no_org.status_code == 400


@pytest.mark.django_db
def test_two_tenant_runtime_isolation(org_with_project):
    _, _, owner = org_with_project
    org_a_id = create_org(owner, 'ot-org-a').json()['runtimeOrganizationId']
    org_b_id = create_org(owner, 'ot-org-b').json()['runtimeOrganizationId']

    project_a = post_json(
        owner, '/open-label/bridge/projects', {'projectId': 'ot-pa', 'openTrainOrganizationId': 'ot-org-a'}
    ).json()
    project_b = post_json(
        owner, '/open-label/bridge/projects', {'projectId': 'ot-pb', 'openTrainOrganizationId': 'ot-org-b'}
    ).json()
    task_b = Task.objects.create(
        project_id=int(project_b['runtimeProjectId']), data={'text': 'tenant b row', 'opentrain_task_id': 'ot-b-1'}
    )

    # Tenant orgs intentionally keep legacy API tokens disabled, so authenticate
    # the tenant user the way shadow users authenticate: with a session.
    tenant_a_user = Organization.objects.get(id=int(org_a_id)).created_by
    client = Client()
    client.force_login(tenant_a_user)
    stamp_session_login(client)

    own_project = client.get(f"/api/projects/{project_a['runtimeProjectId']}/")
    assert own_project.status_code == 200

    cross_project = client.get(f"/api/projects/{project_b['runtimeProjectId']}/")
    assert cross_project.status_code == 404

    cross_task = client.get(f'/api/tasks/{task_b.id}/')
    assert cross_task.status_code in (403, 404)

    listing = client.get('/api/projects/')
    assert listing.status_code == 200
    listed_ids = {str(item['id']) for item in listing.json().get('results', [])}
    assert project_a['runtimeProjectId'] in listed_ids
    assert project_b['runtimeProjectId'] not in listed_ids
    assert int(org_b_id) != int(org_a_id)


@pytest.mark.django_db
def test_bridge_session_cannot_reach_bridge_management_apis(org_with_project):
    organization, project, owner = org_with_project
    client = Client()
    client.force_login(owner)
    stamp_session_login(
        client,
        extra={'open_label_bridge': {'sessionId': 's-1', 'role': 'employer_review', 'projectId': project.id}},
    )

    blocked = client.post(
        '/open-label/bridge/projects',
        data=json.dumps({'projectId': 'ot-escalate'}),
        content_type='application/json',
    )
    assert blocked.status_code == 403

    token_mint = client.post('/api/current-user/token')
    assert token_mint.status_code == 403


@pytest.mark.django_db
def test_active_organization_middleware_prefers_membership_org(org_with_project, django_user_model):
    organization, _, _ = org_with_project
    second_owner = django_user_model.objects.create_user(email='second@example.com', password='pass-1234')
    second_org = Organization.create_organization(created_by=second_owner, title='Second Org')
    member = django_user_model.objects.create_user(email='member@example.com', password='pass-1234')
    second_org.add_user(member)
    assert member.active_organization_id is None or member.active_organization_id == second_org.id
    member.active_organization = None
    member.save(update_fields=['active_organization'])

    client = Client()
    client.force_login(member)
    client.get('/projects/')
    member.refresh_from_db()
    assert member.active_organization_id == second_org.id
