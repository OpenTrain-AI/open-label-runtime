"""Native membership: control-plane member sync, invite lockout, bridge_session flag,
and the unsupported-template filter."""

import json

import pytest
import responses
from django.test import Client
from open_label_bridge.models import BridgeIdentity, BridgeOrganizationLink
from open_label_bridge.tests.utils import CONSUME_URL, launch_payload, make_token
from projects.api import read_templates_and_groups
from rest_framework.authtoken.models import Token

MEMBERS_PATH = '/open-label/bridge/organizations/members'


def auth_headers(user):
    token, _ = Token.objects.get_or_create(user=user)
    return {'HTTP_AUTHORIZATION': f'Token {token.key}'}


def post_members(user, payload):
    return Client().post(MEMBERS_PATH, data=json.dumps(payload), content_type='application/json', **auth_headers(user))


def launch_bridge_client(project, **overrides):
    """Returns a Client holding an authenticated bridge session."""
    client = Client()
    token = make_token(launch_payload(project, **overrides))
    response = client.get('/open-label/launch', {'session': token})
    assert response.status_code == 302
    return client


@pytest.mark.django_db
def test_members_sync_provisions_shadow_users_in_tenant_org(signing_env, org_with_project):
    _, _, owner = org_with_project
    payload = {
        'openTrainOrganizationId': 'ot-org-members',
        'members': [
            {'userId': 'ot-user-a', 'displayName': 'Ada Lovelace'},
            {'userId': 'ot-user-b'},
        ],
    }
    response = post_members(owner, payload)
    assert response.status_code == 200
    data = response.json()
    link = BridgeOrganizationLink.objects.get(opentrain_organization_id='ot-org-members')
    assert data['runtimeOrganizationId'] == str(link.organization_id)
    assert [m['openTrainUserId'] for m in data['members']] == ['ot-user-a', 'ot-user-b']

    identity = BridgeIdentity.objects.get(opentrain_user_id='ot-user-a')
    assert identity.user.first_name == 'Ada'
    assert identity.user.last_name == 'Lovelace'
    assert identity.user.active_organization_id == link.organization_id
    assert link.organization.has_user(identity.user)


@pytest.mark.django_db
def test_members_sync_is_idempotent(signing_env, org_with_project):
    _, _, owner = org_with_project
    payload = {
        'openTrainOrganizationId': 'ot-org-members',
        'members': [{'userId': 'ot-user-a', 'displayName': 'Ada Lovelace'}],
    }
    first = post_members(owner, payload)
    second = post_members(owner, payload)
    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json() == second.json()
    assert BridgeIdentity.objects.filter(opentrain_user_id='ot-user-a').count() == 1


@pytest.mark.django_db
def test_members_sync_validation(signing_env, org_with_project):
    _, _, owner = org_with_project
    assert post_members(owner, {'members': [{'userId': 'x'}]}).status_code == 400
    assert post_members(owner, {'openTrainOrganizationId': 'ot-org-m', 'members': []}).status_code == 400
    assert (
        post_members(owner, {'openTrainOrganizationId': 'ot-org-m', 'members': [{'displayName': 'No Id'}]})
    ).status_code == 400
    unauthenticated = Client().post(
        MEMBERS_PATH,
        data=json.dumps({'openTrainOrganizationId': 'ot-org-m', 'members': [{'userId': 'x'}]}),
        content_type='application/json',
    )
    assert unauthenticated.status_code == 401


@pytest.mark.django_db
@responses.activate
def test_bridge_session_cannot_use_invite_endpoints(signing_env, org_with_project):
    _, project, _ = org_with_project
    responses.add(responses.POST, CONSUME_URL, json={'ok': True}, status=200)
    client = launch_bridge_client(project, actorRole='employer_review', nonce='nonce-invite')

    invite = client.get('/api/invite')
    assert invite.status_code == 403
    reset = client.post('/api/invite/reset-token')
    assert reset.status_code == 403


@pytest.mark.django_db
@responses.activate
def test_whoami_reports_bridge_session(signing_env, org_with_project):
    _, project, owner = org_with_project
    responses.add(responses.POST, CONSUME_URL, json={'ok': True}, status=200)
    client = launch_bridge_client(project, actorRole='employer_review', nonce='nonce-whoami')

    response = client.get('/api/current-user/whoami')
    assert response.status_code == 200
    assert response.json()['bridge_session'] is True

    native = Client().get('/api/current-user/whoami', **auth_headers(owner))
    assert native.status_code == 200
    assert native.json()['bridge_session'] is False


def test_templates_exclude_unsupported_tags():
    templates_and_groups = read_templates_and_groups()
    for config in templates_and_groups['templates']:
        xml = config.get('config', '') or ''
        assert '<Chat' not in xml
        assert '<OcrLabels' not in xml
    assert 'Chat' not in templates_and_groups['groups']
    # groups list still covers every remaining template
    populated = {config.get('group', '') for config in templates_and_groups['templates']}
    assert populated.issubset(set(templates_and_groups['groups']))
