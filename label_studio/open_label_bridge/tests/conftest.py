import pytest
from open_label_bridge.tests.utils import CONTROL_PLANE_BASE, SIGNING_SECRET, WEBHOOK_SECRET
from organizations.models import Organization
from projects.models import Project


@pytest.fixture
def signing_env(monkeypatch):
    monkeypatch.setenv('OPEN_LABEL_SESSION_SIGNING_SECRET', SIGNING_SECRET)
    monkeypatch.setenv('OPEN_LABEL_CONTROL_PLANE_BASE_URL', CONTROL_PLANE_BASE)
    monkeypatch.setenv('OPEN_LABEL_WEBHOOK_SECRET', WEBHOOK_SECRET)
    return SIGNING_SECRET


@pytest.fixture
def org_with_project(db, django_user_model):
    owner = django_user_model.objects.create_user(email='owner@example.com', password='pass-1234')
    organization = Organization.create_organization(
        created_by=owner, title='Bridge Test Org', legacy_api_tokens_enabled=True
    )
    owner.active_organization = organization
    owner.save(update_fields=['active_organization'])
    project = Project.objects.create(
        title='Bridge Test Project',
        label_config='<View></View>',
        organization=organization,
        created_by=owner,
    )
    return organization, project, owner
