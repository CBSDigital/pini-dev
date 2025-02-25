"""Tools for managing shotgrid tasks."""

import logging
import os

from pini import pipe, qt

from . import sg_handler, sg_utils

_LOGGER = logging.getLogger(__name__)
_TASK_KEY = os.environ.get('PINI_SG_TASK_NAME_TOKEN', 'content')
TASK_FIELDS = sorted({
    _TASK_KEY, 'step', 'sg_short_name', 'task_assignees',
    'sg_status_list'})


def create_task(work_dir, force=False):
    """Create a shotgrid task.

    Args:
        work_dir (CPWorkDir): work dir to create task for
        force (bool): create task without confirmation

    Returns:
        (dict): task data
    """
    from pini.pipe import shotgrid

    _proj_s = shotgrid.SGC.find_proj(work_dir.job)
    _ety_s = _proj_s.find_entity(work_dir.entity)

    # Get step data
    _step = task_to_step_name(entity=work_dir.entity, task=work_dir.task)
    _step_s = shotgrid.SGC.find_step(_step)
    assert _step_s
    _step_data = _step_s.data

    # Create task
    _data = {
        "project": _proj_s.to_entry(),
        "entity": _ety_s.to_entry(),
        _TASK_KEY: work_dir.task,
        "step": _step_s.to_entry(),
    }
    if not force:
        qt.ok_cancel(
            f'Register task {work_dir.task} on shotgrid?\n\n'
            f'Step: {_step_data["code"]}\n'
            f'Entity: {work_dir.entity.job.name}/{work_dir.entity.name}',
            icon=sg_utils.ICON, title='Shotgrid')
    sg_handler.create('Task', _data)

    return _ety_s.find_task(work_dir, force=True)


def task_to_step_name(task, entity=None):
    """Map the given task to a pipeline step name.

    Args:
        task (str): task name
        entity (CPEntity): task entity

    Returns:
        (str): step name
    """
    _ety = entity or pipe.cur_entity()
    return {
        'anim': 'Animation',
        'crowd': 'Animation',
        'groom': 'Character FX',
        'env': 'Model',
        'fx': 'FX',
        'layout': 'Animation',
        'lighting': 'Light',
        'lsc': 'Light' if _ety.is_shot else 'Lookdev',
        'precomp': 'Comp',
        'roto': 'Comp',
        'techanim': 'Character FX',
    }.get(task, task.capitalize())
