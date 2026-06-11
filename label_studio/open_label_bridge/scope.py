"""Task-scope enforcement for restricted bridge sessions.

Labeler launch payloads may carry an assignment scope: a dataset id (matched
against task data's opentrain_dataset_id, stamped by the control-plane dataset
sync) and/or an explicit runtime task-id list. Restricted sessions only ever
see tasks inside that scope — querysets are narrowed centrally and task-level
API access is verified against the same rules.
"""

# Reviewers are externally hired QA workers: project-restricted like labelers,
# but they see the whole project's tasks unless a narrower scope is launched.
RESTRICTED_BRIDGE_ROLES = ('candidate', 'labeler', 'reviewer')
SCOPE_TASK_ID_LIMIT = 5000


def normalized_scope_task_ids(raw):
    if not isinstance(raw, list):
        return None
    task_ids = []
    for value in raw[:SCOPE_TASK_ID_LIMIT]:
        if isinstance(value, bool):
            continue
        if isinstance(value, int):
            task_ids.append(value)
        elif isinstance(value, str) and value.isdigit():
            task_ids.append(int(value))
    return task_ids or None


def bridge_session_scope(request):
    if not hasattr(request, 'session'):
        return None
    bridge = request.session.get('open_label_bridge')
    if not isinstance(bridge, dict) or bridge.get('role') not in RESTRICTED_BRIDGE_ROLES:
        return None
    dataset_id = bridge.get('scopeDatasetId')
    task_ids = bridge.get('scopeTaskIds')
    dataset_id = dataset_id if isinstance(dataset_id, str) and dataset_id else None
    task_ids = normalized_scope_task_ids(task_ids)
    if dataset_id is None and task_ids is None:
        return None
    return {'datasetId': dataset_id, 'taskIds': task_ids}


def filter_tasks_for_bridge_session(request, queryset):
    scope = bridge_session_scope(request)
    if scope is None:
        return queryset
    if scope['taskIds'] is not None:
        queryset = queryset.filter(id__in=scope['taskIds'])
    if scope['datasetId'] is not None:
        queryset = queryset.filter(data__opentrain_dataset_id=scope['datasetId'])
    return queryset


def task_allowed_for_bridge_session(request, task_id):
    scope = bridge_session_scope(request)
    if scope is None:
        return True
    try:
        task_id = int(task_id)
    except (TypeError, ValueError):
        return False
    if scope['taskIds'] is not None and task_id not in scope['taskIds']:
        return False
    if scope['datasetId'] is not None:
        from tasks.models import Task

        data = Task.objects.filter(id=task_id).values_list('data', flat=True).first()
        if not isinstance(data, dict) or data.get('opentrain_dataset_id') != scope['datasetId']:
            return False
    return True
