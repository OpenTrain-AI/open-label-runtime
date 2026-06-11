import logging
import os
import time

from core.label_config import validate_label_config
from django.contrib import auth
from django.http import HttpResponse
from django.shortcuts import redirect
from django.views.decorators.http import require_GET
from django.db import transaction
from organizations.models import Organization
from projects.models import Project
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from tasks.models import Task
from webhooks.models import Webhook

from .consume import BridgeConsumeError, consume_nonce
from .identity import ensure_bridge_user
from .models import BridgeIdentity, BridgeProjectLink
from .scope import normalized_scope_task_ids
from .tenancy import ensure_runtime_organization
from .tokens import BridgeTokenError, verify_launch_token

logger = logging.getLogger(__name__)

DENIED_HTML = (
    '<!doctype html><html><head><title>Session unavailable</title></head>'
    '<body style="font-family: sans-serif; margin: 4rem auto; max-width: 28rem; text-align: center;">'
    '<h1 style="font-size: 1.25rem;">This labeling session link is no longer valid</h1>'
    '<p>The link may have expired or already been used. '
    'Return to OpenTrain and relaunch your workspace.</p>'
    '</body></html>'
)


def bridge_denied_response(reason, status_code=403):
    response = HttpResponse(DENIED_HTML, content_type='text/html', status=status_code)
    response['x-open-label-bridge-reason'] = reason
    return response


def resolve_runtime_project(payload):
    runtime_project_id = payload.get('runtimeProjectId')
    if runtime_project_id is None:
        return None
    raw = str(runtime_project_id)
    if not raw.isdigit():
        return None
    return Project.objects.filter(id=int(raw)).first()


def establish_bridge_session(request, payload):
    project = resolve_runtime_project(payload)
    organization = project.organization if project else None
    user = ensure_bridge_user(payload['actorUserId'], organization)
    auth.login(request, user, backend='django.contrib.auth.backends.ModelBackend')
    # InactivitySessionTimeoutMiddleWare logs out sessions without this stamp
    request.session['last_login'] = time.time()
    scope_dataset_id = payload.get('scopeDatasetId')
    request.session['open_label_bridge'] = {
        'sessionId': payload['sessionId'],
        'role': payload['actorRole'],
        'downloadPolicy': payload.get('sourceAssetDownloadPolicy'),
        'projectId': project.id if project else None,
        'assignmentId': payload.get('assignmentId'),
        'scopeDatasetId': scope_dataset_id if isinstance(scope_dataset_id, str) and scope_dataset_id else None,
        'scopeTaskIds': normalized_scope_task_ids(payload.get('scopeRuntimeTaskIds')),
    }
    return project


def bridge_landing_path(payload, project):
    if project is None:
        return '/projects/'
    if payload['actorRole'] in ('candidate', 'labeler'):
        return f'/projects/{project.id}/data?labeling=1'
    return f'/projects/{project.id}/data'


@require_GET
def launch(request):
    token = request.GET.get('session', '')
    try:
        payload = verify_launch_token(token)
    except BridgeTokenError as exc:
        logger.info('open_label_bridge: launch token rejected (%s)', exc.reason)
        return bridge_denied_response(exc.reason)
    try:
        consume_nonce(payload)
    except BridgeConsumeError as exc:
        logger.info('open_label_bridge: launch nonce rejected (%s)', exc.reason)
        return bridge_denied_response(exc.reason)

    project = establish_bridge_session(request, payload)
    return redirect(bridge_landing_path(payload, project))


def _first_string(*values):
    for value in values:
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _extract_label_config(value):
    if isinstance(value, str) and value.strip():
        return value
    if isinstance(value, dict):
        for key in ('xml', 'labelConfig', 'label_config', 'config'):
            nested = value.get(key)
            if isinstance(nested, str) and nested.strip():
                return nested
    return None


def _extract_opentrain_organization_id(data):
    return _first_string(
        data.get('openTrainOrganizationId'),
        data.get('opentrainOrganizationId'),
        data.get('ownerOrganizationId'),
    )


class BridgeOrganizationCreateAPI(APIView):
    """Idempotently provisions a dedicated runtime organization for an OpenTrain tenant."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        data = request.data if isinstance(request.data, dict) else {}
        opentrain_organization_id = _extract_opentrain_organization_id(data)
        if not opentrain_organization_id:
            return Response(
                {'detail': 'openTrainOrganizationId is required'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        organization, created = ensure_runtime_organization(
            opentrain_organization_id, title=_first_string(data.get('title'))
        )
        return Response(
            {
                'runtimeOrganizationId': str(organization.id),
                'openTrainOrganizationId': opentrain_organization_id,
            },
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )


class BridgeProjectCreateAPI(APIView):
    """Accepts the exact provisioning payload the OpenTrain control plane already sends."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        data = request.data if isinstance(request.data, dict) else {}
        opentrain_ref = _first_string(
            data.get('projectId'),
            data.get('assessmentId'),
            data.get('projectVersionId'),
            data.get('assessmentVersionId'),
        )
        task_type = _first_string(data.get('taskType'))
        title_parts = ['Open Label']
        if task_type:
            title_parts.append(task_type)
        if opentrain_ref:
            title_parts.append(opentrain_ref)
        title_max_length = Project._meta.get_field('title').max_length or 50
        title = ' '.join(title_parts)[:title_max_length]

        label_config = _extract_label_config(data.get('labelStudioConfig'))
        instructions = _first_string(data.get('instructions')) or ''
        opentrain_organization_id = _extract_opentrain_organization_id(data)
        if opentrain_organization_id:
            organization, _ = ensure_runtime_organization(opentrain_organization_id)
        else:
            organization = request.user.active_organization or Organization.objects.first()
        if organization is None:
            return Response({'detail': 'No runtime organization available'}, status=status.HTTP_409_CONFLICT)

        try:
            validate_label_config(label_config or '<View></View>')
        except Exception as exc:
            logger.warning('open_label_bridge: invalid label config: %s', exc)
            return Response(
                {'detail': f'Invalid project configuration: {exc}'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            project = Project.objects.create(
                title=title,
                label_config=label_config or '<View></View>',
                expert_instruction=instructions,
                organization=organization,
                created_by=organization.created_by or request.user,
            )
        except Exception as exc:
            logger.warning('open_label_bridge: project create failed: %s', exc)
            return Response(
                {'detail': f'Invalid project configuration: {exc}'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        BridgeProjectLink.objects.create(
            project=project,
            opentrain_assessment_id=_first_string(data.get('assessmentId')),
            opentrain_assessment_version_id=_first_string(data.get('assessmentVersionId')),
            opentrain_project_id=_first_string(data.get('projectId')),
            opentrain_project_version_id=_first_string(data.get('projectVersionId')),
            task_type=task_type,
        )

        webhook_base = os.environ.get('OPEN_LABEL_CONTROL_PLANE_BASE_URL', '').strip().rstrip('/')
        if webhook_base:
            headers = {}
            webhook_secret = os.environ.get('OPEN_LABEL_WEBHOOK_SECRET', '').strip()
            if webhook_secret:
                headers['x-open-label-secret'] = webhook_secret
            Webhook.objects.create(
                organization=organization,
                project=project,
                url=f'{webhook_base}/api/webhooks/open-label',
                headers=headers,
                send_payload=True,
                send_for_all_actions=True,
            )

        runtime_project_url = request.build_absolute_uri(f'/projects/{project.id}')
        return Response(
            {
                'runtimeProjectId': str(project.id),
                'runtimeProjectUrl': runtime_project_url,
                'project': {'id': project.id, 'title': project.title, 'url': runtime_project_url},
            },
            status=status.HTTP_201_CREATED,
        )


BRIDGE_TASK_BATCH_MAX = 1000


class BridgeTaskBatchCreateAPI(APIView):
    """Bulk task create for control-plane dataset sync.

    Accepts {"tasks": [{"openTrainTaskId": str, "data": dict}, ...]} and is
    idempotent on data.opentrain_task_id: entries whose OpenTrain id already
    exists in the project are returned with their existing runtime task id.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request, project_id):
        project = Project.objects.filter(id=project_id).first()
        if project is None:
            return Response({'detail': 'Project not found'}, status=status.HTTP_404_NOT_FOUND)

        data = request.data if isinstance(request.data, dict) else {}
        entries = data.get('tasks')
        if not isinstance(entries, list) or not entries:
            return Response({'detail': 'tasks must be a non-empty list'}, status=status.HTTP_400_BAD_REQUEST)
        if len(entries) > BRIDGE_TASK_BATCH_MAX:
            return Response(
                {'detail': f'tasks exceeds the maximum batch size of {BRIDGE_TASK_BATCH_MAX}'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        normalized = []
        seen_ids = set()
        for index, entry in enumerate(entries):
            record = entry if isinstance(entry, dict) else {}
            opentrain_task_id = _first_string(record.get('openTrainTaskId'), record.get('opentrainTaskId'))
            task_data = record.get('data')
            if not opentrain_task_id or not isinstance(task_data, dict):
                return Response(
                    {'detail': f'tasks[{index}] must include openTrainTaskId and a data object'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if opentrain_task_id in seen_ids:
                return Response(
                    {'detail': f'tasks[{index}] repeats openTrainTaskId {opentrain_task_id}'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            seen_ids.add(opentrain_task_id)
            normalized.append((opentrain_task_id, dict(task_data, opentrain_task_id=opentrain_task_id)))

        existing_by_opentrain_id = {}
        for runtime_task_id, task_data in Task.objects.filter(
            project=project, data__opentrain_task_id__in=list(seen_ids)
        ).values_list('id', 'data'):
            opentrain_task_id = (task_data or {}).get('opentrain_task_id')
            if isinstance(opentrain_task_id, str) and opentrain_task_id not in existing_by_opentrain_id:
                existing_by_opentrain_id[opentrain_task_id] = runtime_task_id

        created = []
        new_tasks = []
        with transaction.atomic():
            for opentrain_task_id, task_data in normalized:
                runtime_task_id = existing_by_opentrain_id.get(opentrain_task_id)
                if runtime_task_id is None:
                    task = Task(project=project, data=task_data)
                    task.save()
                    runtime_task_id = task.id
                    new_tasks.append(task)
                created.append({'openTrainTaskId': opentrain_task_id, 'runtimeTaskId': str(runtime_task_id)})

        if new_tasks:
            if hasattr(project, 'summary'):
                project.summary.update_data_columns(new_tasks)
            project.update_tasks_states(
                maximum_annotations_changed=False,
                overlap_cohort_percentage_changed=False,
                tasks_number_changed=True,
            )

        return Response(
            {'created': created},
            status=status.HTTP_201_CREATED if new_tasks else status.HTTP_200_OK,
        )


BRIDGE_ANNOTATION_PAGE_DEFAULT = 500
BRIDGE_ANNOTATION_PAGE_MAX = 1000


def _positive_int(value, default):
    if value is None:
        return default
    raw = str(value)
    if not raw.isdigit():
        return None
    parsed = int(raw)
    return parsed if parsed >= 1 else None


def _isoformat(value):
    return value.isoformat() if value is not None else None


class BridgeProjectAnnotationsAPI(APIView):
    """Paginated annotation read for control-plane exports.

    Annotators are reported as OpenTrain user ids via BridgeIdentity; runtime
    users without a bridge identity map to null so no runtime identity leaks.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, project_id):
        project = Project.objects.filter(id=project_id).first()
        if project is None:
            return Response({'detail': 'Project not found'}, status=status.HTTP_404_NOT_FOUND)

        page = _positive_int(request.query_params.get('page'), 1)
        page_size = _positive_int(request.query_params.get('pageSize'), BRIDGE_ANNOTATION_PAGE_DEFAULT)
        if page is None or page_size is None:
            return Response(
                {'detail': 'page and pageSize must be positive integers'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        page_size = min(page_size, BRIDGE_ANNOTATION_PAGE_MAX)

        queryset = Task.objects.filter(project=project).order_by('id')
        total = queryset.count()
        offset = (page - 1) * page_size
        tasks = list(queryset.prefetch_related('annotations')[offset : offset + page_size])

        completed_by_ids = {
            annotation.completed_by_id
            for task in tasks
            for annotation in task.annotations.all()
            if annotation.completed_by_id is not None
        }
        opentrain_user_by_runtime_id = dict(
            BridgeIdentity.objects.filter(user_id__in=completed_by_ids).values_list(
                'user_id', 'opentrain_user_id'
            )
        )

        task_payloads = []
        for task in tasks:
            task_data = task.data if isinstance(task.data, dict) else {}
            opentrain_task_id = task_data.get('opentrain_task_id')
            task_payloads.append(
                {
                    'runtimeTaskId': str(task.id),
                    'openTrainTaskId': opentrain_task_id if isinstance(opentrain_task_id, str) else None,
                    'annotations': [
                        {
                            'runtimeAnnotationId': str(annotation.id),
                            'result': annotation.result,
                            'wasCancelled': bool(annotation.was_cancelled),
                            'leadTimeSeconds': annotation.lead_time,
                            'createdAt': _isoformat(annotation.created_at),
                            'updatedAt': _isoformat(annotation.updated_at),
                            'completedByOpenTrainUserId': opentrain_user_by_runtime_id.get(
                                annotation.completed_by_id
                            ),
                        }
                        for annotation in task.annotations.all()
                    ],
                }
            )

        return Response(
            {
                'tasks': task_payloads,
                'total': total,
                'page': page,
                'pageSize': page_size,
                'hasMore': offset + len(tasks) < total,
            },
            status=status.HTTP_200_OK,
        )


class BridgeProjectMoveAPI(APIView):
    """Moves an existing runtime project (and its bridge webhooks) into a tenant organization.

    Used by the control-plane reorg backfill when adopting per-tenant runtime orgs.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request, project_id):
        project = Project.objects.filter(id=project_id).first()
        if project is None:
            return Response({'detail': 'Project not found'}, status=status.HTTP_404_NOT_FOUND)

        data = request.data if isinstance(request.data, dict) else {}
        opentrain_organization_id = _extract_opentrain_organization_id(data)
        if not opentrain_organization_id:
            return Response(
                {'detail': 'openTrainOrganizationId is required'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        organization, _ = ensure_runtime_organization(opentrain_organization_id)
        moved = project.organization_id != organization.id
        if moved:
            with transaction.atomic():
                project.organization = organization
                if organization.created_by is not None:
                    project.created_by = organization.created_by
                project.save(update_fields=['organization', 'created_by'])
                Webhook.objects.filter(project=project).update(organization=organization)

        return Response(
            {
                'runtimeProjectId': str(project.id),
                'runtimeOrganizationId': str(organization.id),
                'moved': moved,
            },
            status=status.HTTP_200_OK,
        )
