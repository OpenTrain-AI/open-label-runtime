"""Bridge middlewares.

BridgeLaunchSessionMiddleware consumes launch tokens carried as ?session= on any
URL (including the already-shipped /projects/<id>?session=... shape) and converts
them into an authenticated runtime session.

BridgeAccessMiddleware restricts candidate sessions to their own project and away
from export/storage/settings/org/webhook/member surfaces.
"""

import logging
import re

from django.http import JsonResponse
from django.shortcuts import redirect

from .consume import BridgeConsumeError, consume_nonce
from .tokens import BridgeTokenError, verify_launch_token

logger = logging.getLogger(__name__)

LAUNCH_PATH = '/open-label/launch'

CANDIDATE_BLOCKED_PATTERNS = [
    re.compile(r'^/api/storages'),
    re.compile(r'^/api/webhooks'),
    re.compile(r'^/api/invite'),
    re.compile(r'^/api/organizations'),
    re.compile(r'^/api/users'),
    re.compile(r'^/api/current-user/(token|reset-token)'),
    re.compile(r'^/api/projects/\d+/exports?'),
    re.compile(r'^/api/projects/\d+/file-uploads'),
    re.compile(r'^/api/import'),
    re.compile(r'^/admin'),
    re.compile(r'^/organization'),
]

CANDIDATE_BLOCKED_WRITE_PATTERNS = [
    re.compile(r'^/api/projects/\d+/?$'),
]

PROJECT_PATH_PATTERN = re.compile(r'^/(?:api/)?projects/(\d+)')


def _stripped_redirect(request):
    params = request.GET.copy()
    params.pop('session', None)
    params.pop('downloadPolicy', None)
    query = params.urlencode()
    return redirect(f'{request.path}?{query}' if query else request.path)


class BridgeLaunchSessionMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        token = request.GET.get('session')
        if token and request.method == 'GET' and request.path != LAUNCH_PATH:
            return self._handle_token(request, token)
        return self.get_response(request)

    def _handle_token(self, request, token):
        from .views import establish_bridge_session

        try:
            payload = verify_launch_token(token)
        except BridgeTokenError as exc:
            return self._reject(request, exc.reason)
        try:
            consume_nonce(payload)
        except BridgeConsumeError as exc:
            return self._reject(request, exc.reason)

        establish_bridge_session(request, payload)
        return _stripped_redirect(request)

    def _reject(self, request, reason):
        from .views import bridge_denied_response

        # An already-authenticated user keeps their own session; just strip the token.
        if request.user.is_authenticated:
            return _stripped_redirect(request)
        logger.info('open_label_bridge: rejected launch token (%s)', reason)
        return bridge_denied_response(reason)


class BridgeAccessMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        bridge = request.session.get('open_label_bridge') if hasattr(request, 'session') else None
        if bridge and request.user.is_authenticated and bridge.get('role') == 'candidate':
            denial = self._check_candidate(request, bridge)
            if denial is not None:
                return denial
        return self.get_response(request)

    def _check_candidate(self, request, bridge):
        path = request.path
        for pattern in CANDIDATE_BLOCKED_PATTERNS:
            if pattern.match(path):
                return self._deny(path)
        if request.method not in ('GET', 'HEAD', 'OPTIONS'):
            for pattern in CANDIDATE_BLOCKED_WRITE_PATTERNS:
                if pattern.match(path):
                    return self._deny(path)
        allowed_project_id = bridge.get('projectId')
        if allowed_project_id is not None:
            match = PROJECT_PATH_PATTERN.match(path)
            if match and int(match.group(1)) != allowed_project_id:
                return self._deny(path)
        return None

    def _deny(self, path):
        logger.info('open_label_bridge: blocked candidate access to %s', path)
        return JsonResponse({'detail': 'Not available in this labeling session.'}, status=403)
