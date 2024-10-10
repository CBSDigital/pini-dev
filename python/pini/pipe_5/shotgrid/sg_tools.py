"""Tools for managing shotgrid integration."""

import logging
import os

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

    if os.environ.get('PINI_SG_DISABLE_UPDATE_TASK'):
        return

    _work = work or pipe.CACHE.cur_work
    _update_data = {}

    # Read task
    _task = shotgrid.SGC.find_task(path=_work.work_dir.path)
    _task_data = shotgrid.find_one(
        'Task', id_=_task.id_, fields=['task_assignees'])
    _LOGGER.debug(' - TASK DATA %s', _task_data)

    # Check if user update needed
    _task_assignees = _task_data['task_assignees']
    _LOGGER.debug(' - TASK ASSIGNEES %s', _task_assignees)
    _user = shotgrid.SGC.find_user()
    _LOGGER.debug(' - USER DATA %s', _user.to_entry())
    for _assignee in _task_assignees:
        if _assignee['id'] == _user.id_:
            _LOGGER.debug(' - USER ALREADY ASSIGNED')
            break
    else:
        _LOGGER.debug(' - UPDATING USER')
        _task_assignees.append(_user.to_entry())
        _update_data['task_assignees'] = _task_assignees

    # Check if status update needed
    if _task.status in ['wtg', 'ready']:
        _update_data['sg_status_list'] = 'ip'

    # Apply update
    if _update_data:
        shotgrid.update('Task', _task.id_, _update_data)
        _LOGGER.debug(' - UPDATED SHOTGRID')
    else:
        _LOGGER.debug(' - NO UPDATE REQUIRED')
