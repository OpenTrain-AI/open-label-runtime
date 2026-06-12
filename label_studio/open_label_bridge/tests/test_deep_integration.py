"""Tests for deep-integration v4 bridge additions: avatar sync, job-link mirror, instruction PATCH."""

import json

import pytest
from django.test import Client
from open_label_bridge.identity import ensure_bridge_user, normalized_avatar_url
from open_label_bridge.models import BridgeIdentity, BridgeProjectLink
from projects.serializers import ProjectSerializer
from rest_framework.authtoken.models import Token

MEMBERS_PATH = '/open-label/bridge/organizations/members'

AVATAR_URL = 'https://cdn.opentrain.test/profile-photos/weston.png'
AVATAR_URL_2 = 'https://cdn.opentrain.test/profile-photos/weston-2.png'


def auth_headers(user):
    token, _ = Token.objects.get_or_create(user=user)
    return {'HTTP_AUTHORIZATION': f'Token {token.key}'}


def post_members(user, members):
    client = Client()
    return client.post(
        MEMBERS_PATH,
        data=json.dumps({'openTrainOrganizationId': 'ot-org-deep', 'members': members}),
        content_type='application/json',
        **auth_headers(user),
    )


def patch_json(user, path, payload):
    client = Client()
    return client.patch(
        path,
        data=json.dumps(payload),
        content_type='application/json',
        **auth_headers(user),
    )


class TestNormalizedAvatarUrl:
    def test_none_means_leave_unchanged(self):
        assert normalized_avatar_url(None) is None

    def test_empty_string_means_clear(self):
        assert normalized_avatar_url('') == ''
        assert normalized_avatar_url('   ') == ''

    def test_valid_https_url(self):
        assert normalized_avatar_url(AVATAR_URL) == AVATAR_URL

    def test_http_rejected(self):
        assert normalized_avatar_url('http://cdn.opentrain.test/a.png') is None

    def test_non_string_rejected(self):
        assert normalized_avatar_url(123) is None

    def test_too_long_rejected(self):
        long_url = 'https://cdn.opentrain.test/' + 'a' * 1024
        assert normalized_avatar_url(long_url) is None


@pytest.mark.django_db
class TestMembersAvatarSync:
    def test_member_avatar_url_is_stored_and_preferred(self, signing_env, org_with_project):
        organization, _, owner = org_with_project
        response = post_members(
            owner,
            [{'userId': 'ot-user-1', 'displayName': 'Weston Hamilton', 'avatarUrl': AVATAR_URL}],
        )
        assert response.status_code == 200, response.content
        identity = BridgeIdentity.objects.get(opentrain_user_id='ot-user-1')
        identity.user.refresh_from_db()
        assert identity.user.external_avatar_url == AVATAR_URL
        assert identity.user.avatar_url == AVATAR_URL

    def test_member_avatar_url_updates_on_change(self, signing_env, org_with_project):
        organization, _, owner = org_with_project
        post_members(owner, [{'userId': 'ot-user-2', 'displayName': 'A B', 'avatarUrl': AVATAR_URL}])
        response = post_members(owner, [{'userId': 'ot-user-2', 'displayName': 'A B', 'avatarUrl': AVATAR_URL_2}])
        assert response.status_code == 200, response.content
        identity = BridgeIdentity.objects.get(opentrain_user_id='ot-user-2')
        identity.user.refresh_from_db()
        assert identity.user.external_avatar_url == AVATAR_URL_2

    def test_member_avatar_url_empty_string_clears(self, signing_env, org_with_project):
        organization, _, owner = org_with_project
        post_members(owner, [{'userId': 'ot-user-3', 'displayName': 'A B', 'avatarUrl': AVATAR_URL}])
        response = post_members(owner, [{'userId': 'ot-user-3', 'displayName': 'A B', 'avatarUrl': ''}])
        assert response.status_code == 200, response.content
        identity = BridgeIdentity.objects.get(opentrain_user_id='ot-user-3')
        identity.user.refresh_from_db()
        assert identity.user.external_avatar_url == ''

    def test_member_avatar_url_omitted_leaves_existing(self, signing_env, org_with_project):
        organization, _, owner = org_with_project
        post_members(owner, [{'userId': 'ot-user-4', 'displayName': 'A B', 'avatarUrl': AVATAR_URL}])
        response = post_members(owner, [{'userId': 'ot-user-4', 'displayName': 'A B'}])
        assert response.status_code == 200, response.content
        identity = BridgeIdentity.objects.get(opentrain_user_id='ot-user-4')
        identity.user.refresh_from_db()
        assert identity.user.external_avatar_url == AVATAR_URL

    def test_member_avatar_url_http_rejected(self, signing_env, org_with_project):
        organization, _, owner = org_with_project
        response = post_members(
            owner, [{'userId': 'ot-user-5', 'displayName': 'A B', 'avatarUrl': 'http://insecure.test/a.png'}]
        )
        assert response.status_code == 400
        assert 'avatarUrl' in response.json()['detail']

    def test_member_avatar_url_too_long_rejected(self, signing_env, org_with_project):
        organization, _, owner = org_with_project
        long_url = 'https://cdn.opentrain.test/' + 'a' * 1024
        response = post_members(owner, [{'userId': 'ot-user-6', 'displayName': 'A B', 'avatarUrl': long_url}])
        assert response.status_code == 400
        assert 'avatarUrl' in response.json()['detail']


@pytest.mark.django_db
class TestEnsureBridgeUserAvatar:
    def test_avatar_set_and_cleared(self, org_with_project):
        organization, _, _ = org_with_project
        user = ensure_bridge_user('ot-user-7', organization, display_name='C D', avatar_url=AVATAR_URL)
        user.refresh_from_db()
        assert user.external_avatar_url == AVATAR_URL

        user = ensure_bridge_user('ot-user-7', organization, display_name='C D', avatar_url='')
        user.refresh_from_db()
        assert user.external_avatar_url == ''

    def test_invalid_avatar_leaves_existing(self, org_with_project):
        organization, _, _ = org_with_project
        ensure_bridge_user('ot-user-8', organization, avatar_url=AVATAR_URL)
        user = ensure_bridge_user('ot-user-8', organization, avatar_url='http://bad.test/a.png')
        user.refresh_from_db()
        assert user.external_avatar_url == AVATAR_URL


@pytest.mark.django_db
class TestJobLinkMirror:
    def job_link_path(self, project):
        return f'/open-label/bridge/projects/{project.id}/job-link'

    def test_upsert_and_serializer_field(self, signing_env, org_with_project):
        _, project, owner = org_with_project
        response = patch_json(
            owner,
            self.job_link_path(project),
            {'jobId': 'job-123', 'jobTitle': 'Image QA', 'mode': 'production'},
        )
        assert response.status_code == 200, response.content
        body = response.json()
        assert body['opentrainJob'] == {'jobId': 'job-123', 'jobTitle': 'Image QA', 'mode': 'production'}

        link = BridgeProjectLink.objects.get(project=project)
        assert link.linked_job_id == 'job-123'
        assert link.linked_job_title == 'Image QA'
        assert link.linked_job_mode == 'production'

        project.refresh_from_db()
        data = ProjectSerializer(project).data
        assert data['opentrain_job'] == {'jobId': 'job-123', 'jobTitle': 'Image QA', 'mode': 'production'}

    def test_clear(self, signing_env, org_with_project):
        _, project, owner = org_with_project
        patch_json(owner, self.job_link_path(project), {'jobId': 'job-123', 'jobTitle': 'T', 'mode': 'screening'})
        response = patch_json(owner, self.job_link_path(project), {'jobId': None})
        assert response.status_code == 200, response.content
        assert response.json()['opentrainJob'] is None

        link = BridgeProjectLink.objects.get(project=project)
        assert link.linked_job_id is None
        assert link.linked_job_title is None
        assert link.linked_job_mode is None

        project.refresh_from_db()
        data = ProjectSerializer(project).data
        assert data['opentrain_job'] is None

    def test_invalid_mode_rejected(self, signing_env, org_with_project):
        _, project, owner = org_with_project
        response = patch_json(owner, self.job_link_path(project), {'jobId': 'job-1', 'mode': 'bogus'})
        assert response.status_code == 400
        assert 'mode' in response.json()['detail']

    def test_unlinked_project_serializes_null(self, org_with_project):
        _, project, _ = org_with_project
        data = ProjectSerializer(project).data
        assert data['opentrain_job'] is None

    def test_missing_project_404(self, signing_env, org_with_project):
        _, _, owner = org_with_project
        response = patch_json(owner, '/open-label/bridge/projects/999999/job-link', {'jobId': 'job-1'})
        assert response.status_code == 404


@pytest.mark.django_db
class TestInstructionPatch:
    def project_path(self, project):
        return f'/open-label/bridge/projects/{project.id}'

    def test_expert_instruction_sanitized(self, signing_env, org_with_project):
        _, project, owner = org_with_project
        html = '<h1>Guide</h1><script>alert(1)</script><p>Label <strong>carefully</strong>.</p>'
        response = patch_json(
            owner, self.project_path(project), {'expert_instruction': html, 'show_instruction': True}
        )
        assert response.status_code == 200, response.content
        project.refresh_from_db()
        assert '<script>' not in project.expert_instruction
        assert '<h1>Guide</h1>' in project.expert_instruction
        assert '<strong>carefully</strong>' in project.expert_instruction
        assert project.show_instruction is True

    def test_show_instruction_false(self, signing_env, org_with_project):
        _, project, owner = org_with_project
        project.show_instruction = True
        project.save(update_fields=['show_instruction'])
        response = patch_json(owner, self.project_path(project), {'show_instruction': False})
        assert response.status_code == 200, response.content
        project.refresh_from_db()
        assert project.show_instruction is False

    def test_image_and_table_survive_sanitization(self, signing_env, org_with_project):
        _, project, owner = org_with_project
        html = '<img src="https://cdn.opentrain.test/i.png" alt="x"><table><tr><td>cell</td></tr></table>'
        response = patch_json(owner, self.project_path(project), {'expert_instruction': html})
        assert response.status_code == 200, response.content
        project.refresh_from_db()
        assert '<img' in project.expert_instruction
        assert '<table>' in project.expert_instruction

    def test_get_returns_instruction_state(self, signing_env, org_with_project):
        _, project, owner = org_with_project
        project.expert_instruction = '<h1>Existing guide</h1>'
        project.show_instruction = True
        project.save(update_fields=['expert_instruction', 'show_instruction'])

        client = Client()
        response = client.get(self.project_path(project), **auth_headers(owner))
        assert response.status_code == 200, response.content
        data = response.json()
        assert data['runtimeProjectId'] == str(project.id)
        assert data['expert_instruction'] == '<h1>Existing guide</h1>'
        assert data['show_instruction'] is True

    def test_get_empty_instruction_defaults(self, signing_env, org_with_project):
        _, project, owner = org_with_project
        client = Client()
        response = client.get(self.project_path(project), **auth_headers(owner))
        assert response.status_code == 200, response.content
        data = response.json()
        assert data['expert_instruction'] == ''
        assert data['show_instruction'] is False

    def test_get_missing_project_404(self, signing_env, org_with_project):
        _, _, owner = org_with_project
        client = Client()
        response = client.get('/open-label/bridge/projects/999999', **auth_headers(owner))
        assert response.status_code == 404
