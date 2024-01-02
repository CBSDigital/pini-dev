"""Tools for managing shotgrid tasks."""

import logging
import os
import pprint

from pini import pipe, qt
from pini.utils import (
    single, assert_eq, cache_result, get_result_cacher, check_heart)

from . import sg_step, sg_handler, sg_entity, sg_job, sg_utils

_LOGGER = logging.getLogger(__name__)
_TASK_KEY = os.environ.get('PINI_SG_TASK_NAME_TOKEN', 'content')
_TASK_FIELDS = sorted({
    _TASK_KEY, 'step', 'sg_short_name', 'task_assignees',
    'sg_status_list'})


def _create_task(work_dir, force=False):
    """Create a shotgrid task.

    Args:
        work_dir (CPWorkDir): work dir to create task for
        force (bool): create task without confirmation

    Returns:
        (dict): task data
    """

    # Get step data
    _step = task_to_step_name(entity=work_dir.entity, task=work_dir.task)
    _step_data = sg_step.to_step_data(
        step=_step, entity_type=work_dir.entity.profile.capitalize())
    assert _step_data

    # Create task
    _data = {
        "project": sg_job.to_job_data(work_dir.entity.job),
        "entity": sg_entity.to_entity_data(work_dir.entity),
        _TASK_KEY: work_dir.task,
        "step": _step_data,
    }
    if not force:
        qt.ok_cancel(
            'Register task {} on shotgrid?\n\nStep: {}\nEntity: {}/{}'.format(
                work_dir.task, _step_data['code'], work_dir.entity.job.name,
                work_dir.entity.name),
            icon=sg_utils.ICON, title='Shotgrid')
    sg_handler.create('Task', _data)

    # Find new data
    _filters = [
        sg_entity.to_entity_filter(work_dir.entity),
        (_TASK_KEY, 'is', work_dir.task)]
    _task_data = single(
        sg_handler.find('Task', filters=_filters, fields=_TASK_FIELDS),
        catch=True)

    return _task_data


@cache_result
def _read_step_names():
    """Read pipeline step name mappings.

    Returns:
        (dict): id -> short name mappings
    """
    _data = sg_handler.find('Step', fields=['short_name'])
    _result = {_item['id']: _item['short_name'] for _item in _data}
    return _result


def find_tasks(entity):
    """Find shotgrid tasks data.

    Args:
        entity (CPEntity): entity to search

    Returns:
        (tuple list): task data (task, label, step)
    """
    check_heart()

    _LOGGER.info('FIND TASKS %s', entity)

    _data = sg_handler.find(
        'Task', filters=[sg_entity.to_entity_filter(entity)],
        fields=_TASK_FIELDS)

    _tmpl = entity.find_template('work_dir')
    _LOGGER.debug(' - TMPL %s', _tmpl)

    _work_dirs = []
    for _item in _data:
        _LOGGER.debug(' - ADDING %s', _item)

        # Determine name/label/step
        _name = _item['sg_short_name']
        if not _name:
            continue
        _task = _item[_TASK_KEY]
        if not _item['step']:
            continue
        _step = _read_step_names()[_item['step']['id']]
        _path = _tmpl.format(task=_task, step=_step, entity_path=entity.path)
        _LOGGER.debug('   - PATH %s', _path)

        try:
            _work_dir = pipe.CPWorkDir(_path, entity=entity)
        except ValueError:
            _LOGGER.debug('   - REJECTED')
            continue
        _LOGGER.debug('   - WORK DIR %s', _work_dir)

        _work_dir_to_task_data(
            _work_dir, data=[_item], force=True)  # Update cache

        _work_dirs.append(_work_dir)

    return sorted(_work_dirs)


@get_result_cacher(use_args=['work_dir'])
def _work_dir_to_task_data(work_dir, data=None, force=False):
    """Request task data from shotgrid.

    Args:
        work_dir (CPWorkDir): work dir to read
        data (dict): force data into cache
        force (bool): create task without confirmation if missing

    Returns:
        (dict): task data
    """
    from pini.pipe import shotgrid

    assert isinstance(work_dir, pipe.CPWorkDir)

    _LOGGER.debug('FIND TASK DATA')

    # Set fields + filters
    _filters = [
        shotgrid.to_entity_filter(work_dir.entity),
        (_TASK_KEY, 'is', work_dir.task),
        ('step', 'is_not', None),
    ]
    _LOGGER.debug(' - FILTERS %s', _filters)

    # Read data
    _task_datas = data or sg_handler.find(
        'Task', filters=_filters, fields=_TASK_FIELDS)
    if len(_task_datas) not in (0, 1):
        pprint.pprint(_task_datas)
        raise RuntimeError('Duplicate tasks')
    _task_data = single(_task_datas, catch=True)
    _LOGGER.debug(' - TASK %s', _task_data)
    if pipe.MASTER == 'disk' and not _task_data:
        _task_data = _create_task(
            work_dir=work_dir, force=force)
    assert _task_data

    # Check step
    if pipe.MASTER == 'disk':
        if _task_data[_TASK_KEY] != work_dir.task:
            raise RuntimeError(_task_data[_TASK_KEY], work_dir.task)
        _step = task_to_step_name(work_dir.task)
        _step_data = shotgrid.to_step_data(
            step=_step, entity_type=work_dir.entity.profile.capitalize())
        _LOGGER.debug('STEP DATA %s', _step_data)
        assert _step_data
        assert_eq(_task_data['step']['id'], _step_data['id'])
        del _task_data['step']

    return _task_data


def _output_to_task_data(output):
    """Obtain task data for the given out.

    Args:
        output (CPOutput): mov to obtain task data for

    Returns:
        (dict): shotgrid task data
    """
    if output.type_ == 'plate_mov':
        _task = 'plate'
    else:
        _task = output.task
    _work_dir = output.entity.to_work_dir(task=_task)
    return _work_dir_to_task_data(_work_dir)


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


def to_task_data(obj, force=False):
    """Obtain task data for the given pipe object.

    Args:
        obj (any): pipeline object to get task data from
        force (bool): create task without confirmation if missing

    Returns:
        (dict): shotgrid task data
    """
    if isinstance(obj, pipe.CPWork):
        return _work_to_task_data(obj)
    if isinstance(obj, pipe.CPOutputBase):
        return _output_to_task_data(obj)
    if isinstance(obj, pipe.CPWorkDir):
        return _work_dir_to_task_data(obj, force=force)
    raise ValueError(object)


def to_task_filter(obj):
    """Obtain task filter for the given object.

    Args:
        obj (any): pipeline object to get task data from

    Returns:
        (tuple): task filter
    """
    _id = to_task_id(obj)
    return ('task', 'is', {'id': _id, 'type': 'Task'})


def to_task_id(obj):
    """Obtain task id for the given pipe object.

    Args:
        obj (any): pipeline object to get task data from

    Returns:
        (int): task id
    """
    return to_task_data(obj)['id']


def _work_to_task_data(work):
    """Obtain task data from the given work file.

    Args:
        work (CPWork): work file to read

    Returns:
        (dict): shotgrid task data
    """
    return _work_dir_to_task_data(work.work_dir)
