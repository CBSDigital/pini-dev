"""Tools for managing shotgrid integration."""

import logging

from pini import pipe

_LOGGER = logging.getLogger(__name__)


def update_work_task(work=None):
    """Update shotgrid task for the given work file.

    This makes sure the current user is assigned to the task, and if the
    task status is "ready" or "waiting", it's updated to "in progress".

    Args:
        work (CPWork): work to update task for
    """
    from pini.pipe import shotgrid
    _LOGGER.debug('UPDATE WORK TASK %s', work)

    _work = work or pipe.CACHE.cur_work
    _update_data = {}

    # Read task
    _task_data = shotgrid.to_task_data(_work)
    _LOGGER.debug(' - TASK DATA %s', _task_data)
    _task_id = _task_data['id']
    _LOGGER.debug(' - TASK ID %s', _task_id)

    # Check if user update needed
    _task_assignees = _task_data['task_assignees']
    _LOGGER.debug(' - TASK ASSIGNEES %s', _task_assignees)
    _user_data = shotgrid.to_user_data()
    _LOGGER.debug(' - USER DATA %s', _user_data)
    for _assignee in _task_assignees:
        if _assignee['id'] == _user_data['id']:
            _LOGGER.debug(' - USER ALREADY ASSIGNED')
            break
    else:
        _LOGGER.debug(' - UPDATING USER')
        _task_assignees.append(_user_data)
        _update_data['task_assignees'] = _task_assignees

    # Check if status update needed
    _status = _task_data['sg_status_list']
    if _status in ['wtg', 'ready']:
        _update_data['sg_status_list'] = 'ip'

    # Apply update
    if _update_data:
        shotgrid.update('Task', _task_id, _update_data)
        _LOGGER.debug(' - UPDATED SHOTGRID')
    else:
        _LOGGER.debug(' - NO UPDATE REQUIRED')
