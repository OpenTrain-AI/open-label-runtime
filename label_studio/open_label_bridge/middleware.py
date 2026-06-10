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
from organizations.models import Organization

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

# Blocked for EVERY bridge session (candidate and employer_review alike):
# shadow users must never reach the control-plane management API or mint
# long-lived DRF tokens that would outlive their scoped launch session.
BRIDGE_SESSION_BLOCKED_PATTERNS = [
    re.compile(r'^/open-label/bridge'),
    re.compile(r'^/api/current-user/(token|reset-token)'),
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
        if bridge and request.user.is_authenticated:
            for pattern in BRIDGE_SESSION_BLOCKED_PATTERNS:
                if pattern.match(request.path):
                    return self._deny(request.path)
            if bridge.get('role') == 'candidate':
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
        logger.info('open_label_bridge: blocked bridge session access to %s', path)
        return JsonResponse({'detail': 'Not available in this labeling session.'}, status=403)


class BridgeActiveOrganizationMiddleware:
    """Tenancy-aware replacement for organizations.middleware.DummyGetSessionMiddleware.

    The stock middleware forced every user into Organization.objects.first(),
    which breaks per-tenant runtime orgs. This version backfills a missing
    active_organization from the user's own memberships first and only falls
    back to the first org for legacy single-org accounts.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, 'user', None)
        if user is not None and user.is_authenticated:
            if user.active_organization is None:
                organization = (
                    user.organizations.filter(organizationmember__deleted_at__isnull=True).first()
                    or Organization.objects.first()
                )
                if organization is not None:
                    user.active_organization = organization
                    user.save(update_fields=['active_organization'])
            if (
                user.active_organization_id is not None
                and request.session.get('organization_pk') != user.active_organization_id
            ):
                request.session['organization_pk'] = user.active_organization_id
        return self.get_response(request)
