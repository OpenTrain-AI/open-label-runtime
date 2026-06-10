import logging
import os
import time

from core.label_config import validate_label_config
from django.contrib import auth
from django.http import HttpResponse
from django.shortcuts import redirect
from django.views.decorators.http import require_GET
from organizations.models import Organization
from projects.models import Project
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from webhooks.models import Webhook

from .consume import BridgeConsumeError, consume_nonce
from .identity import ensure_bridge_user
from .models import BridgeProjectLink
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
    request.session['open_label_bridge'] = {
        'sessionId': payload['sessionId'],
        'role': payload['actorRole'],
        'downloadPolicy': payload.get('sourceAssetDownloadPolicy'),
        'projectId': project.id if project else None,
    }
    return project


def bridge_landing_path(payload, project):
    if project is None:
        return '/projects/'
    if payload['actorRole'] == 'candidate':
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
        title = ' '.join(title_parts)[:120]

        label_config = _extract_label_config(data.get('labelStudioConfig'))
        instructions = _first_string(data.get('instructions')) or ''
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
                created_by=request.user,
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
