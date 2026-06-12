from django.urls import path

from . import views

app_name = 'open_label_bridge'

urlpatterns = [
    path('open-label/launch', views.launch, name='open-label-launch'),
    path(
        'open-label/bridge/organizations',
        views.BridgeOrganizationCreateAPI.as_view(),
        name='open-label-bridge-organizations',
    ),
    path(
        'open-label/bridge/organizations/members',
        views.BridgeOrganizationMembersAPI.as_view(),
        name='open-label-bridge-organization-members',
    ),
    path('open-label/bridge/projects', views.BridgeProjectCreateAPI.as_view(), name='open-label-bridge-projects'),
    path(
        'open-label/bridge/projects/<int:project_id>',
        views.BridgeProjectUpdateAPI.as_view(),
        name='open-label-bridge-project-update',
    ),
    path(
        'open-label/bridge/projects/<int:project_id>/link',
        views.BridgeProjectLinkAPI.as_view(),
        name='open-label-bridge-project-link',
    ),
    path(
        'open-label/bridge/projects/<int:project_id>/job-link',
        views.BridgeProjectJobLinkAPI.as_view(),
        name='open-label-bridge-project-job-link',
    ),
    path(
        'open-label/bridge/projects/<int:project_id>/organization',
        views.BridgeProjectMoveAPI.as_view(),
        name='open-label-bridge-project-move',
    ),
    path(
        'open-label/bridge/projects/<int:project_id>/tasks',
        views.BridgeTaskBatchCreateAPI.as_view(),
        name='open-label-bridge-project-tasks',
    ),
    path(
        'open-label/bridge/projects/<int:project_id>/annotations',
        views.BridgeProjectAnnotationsAPI.as_view(),
        name='open-label-bridge-project-annotations',
    ),
]
