"""Tools for managing shotgrid tasks."""

import logging
import os
import pprint

from pini import pipe, qt
from pini.utils import single, assert_eq, cache_result

from . import sg_step, sg_handler, sg_entity, sg_user

_LOGGER = logging.getLogger(__name__)
_TASK_KEY = os.environ.get('PINI_SG_TASK_NAME_TOKEN', 'content')


def _create_task(entity, task, force=False):
    """Create a shotgrid task.

    Args:
        entity (CPEntity): task entity
        task (str): task name
        force (bool): create task without confirmation

    Returns:
        (dict): task data
    """
    from pini.pipe import shotgrid

    _sg = shotgrid.to_handler()

    # Get step data
    _step = task_to_step_name(entity=entity, task=task)
    _step_data = sg_step.to_step_data(
        step=_step, entity_type=entity.profile.capitalize())
    assert _step_data

    # Create task
    _data = {
        "project": shotgrid.to_job_data(entity.job),
        "entity": shotgrid.to_entity_data(entity),
        _TASK_KEY: task,
        "step": _step_data,
    }
    if not force:
        qt.ok_cancel(
            'Register task {} on shotgrid?\n\nStep: {}\nEntity: {}/{}'.format(
                task, _step_data['code'], entity.job.name, entity.name),
            icon=shotgrid.ICON, title='Shotgrid')
    _sg.create('Task', _data)

    # Find new data
    _filters = [
        shotgrid.to_entity_filter(entity),
        (_TASK_KEY, 'is', task)]
    _task_data = single(
        _sg.find('Task', filters=_filters, fields=[_TASK_KEY, 'step']),
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


def _task_sort(data):
    """Apply task sort to task data.

    Args:
        data (tuple): task data (name, label, step)

    Returns:
        (str): sort key
    """
    _, _label, _, _ = data
    return pipe.task_sort(_label)


def find_tasks(entity):
    """Find shotgrid tasks data.

    Args:
        entity (CPEntity): entity to search

    Returns:
        (tuple list): task data (task, label, step)
    """
    _LOGGER.info('FIND TASKS %s', entity)
    _data = sg_handler.find(
        'Task', filters=[sg_entity.to_entity_filter(entity)],
        fields=['sg_short_name', _TASK_KEY, 'step', 'task_assignees'])
    _results = []
    for _item in _data:
        _LOGGER.debug(' - ADDING %s', _item)

        # Determine name/label/step
        _name = _item['sg_short_name']
        if not _name:
            continue
        _label = _item[_TASK_KEY]
        if not _item['step']:
            continue
        _step = _read_step_names()[_item['step']['id']]

        # Read users/logins
        _assignees = _item['task_assignees']
        _LOGGER.debug('   - ASSIGNEES %s', _assignees)
        _ids = [_user['id'] for _user in _assignees]
        _LOGGER.debug('   - IDS %s', _ids)
        _logins = filter(bool, [
            sg_user.to_user_data(_id).get('login') for _id in _ids])
        _LOGGER.debug('   - LOGINS %s', _logins)

        _results.append((_name, _label, _step, _logins))

    return sorted(_results, key=_task_sort)


def _find_task_data(task, entity, fields=(), force=False):
    """Request task data from shotgrid.

    Args:
        task (str): task name
        entity (CPEntity): parent entity
        fields (tuple): fields to request
        force (bool): create task without confirmation if missing

    Returns:
        (dict): task data
    """
    from pini.pipe import shotgrid

    _LOGGER.debug('FIND TASK DATA')

    # Set fields + filters
    _fields = {_TASK_KEY, 'step'}
    for _field in fields:
        _fields.add(_field)
    _fields = sorted(_fields)
    _LOGGER.debug(' - FIELDS %s', _fields)
    _filters = [
        shotgrid.to_entity_filter(entity),
        (_TASK_KEY, 'is', task),
        ('step', 'is_not', None),
    ]
    _LOGGER.debug(' - FILTERS %s', _filters)

    # Read data
    _task_datas = sg_handler.find('Task', filters=_filters, fields=_fields)
    if len(_task_datas) not in (0, 1):
        pprint.pprint(_task_datas)
        raise RuntimeError('Duplicate tasks')
    _task_data = single(_task_datas, catch=True)
    _LOGGER.debug(' - TASK %s', _task_data)
    if pipe.MASTER == 'disk' and not _task_data:
        _task_data = _create_task(
            entity=entity, task=task, force=force)  # pylint: disable=assignment-from-no-return
    assert _task_data

    # Check step
    if pipe.MASTER == 'disk':
        if _task_data[_TASK_KEY] != task:
            raise RuntimeError(_task_data[_TASK_KEY], task)
        _step = task_to_step_name(entity=entity, task=task)
        _step_data = shotgrid.to_step_data(
            step=_step, entity_type=entity.profile.capitalize())
        _LOGGER.debug('STEP DATA %s', _step_data)
        assert _step_data
        assert_eq(_task_data['step']['id'], _step_data['id'])
        del _task_data['step']

    return _task_data


def _output_to_task_data(output, fields=()):
    """Obtain task data for the given out.

    Args:
        output (CPOutput): mov to obtain task data for
        fields (tuple): fields to request

    Returns:
        (dict): shotgrid task data
    """
    if output.type_ == 'plate_mov':
        _task = 'plate'
    elif output.type_ in [
            'render_mov', 'blast_mov', 'mov', 'cache', 'publish', 'render']:
        _task = output.task
    else:
        raise ValueError(output.type_)
    return _find_task_data(
        task=_task, entity=output.entity, fields=fields)


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


def to_task_data(obj, fields=(), force=False):
    """Obtain task data for the given pipe object.

    Args:
        obj (any): pipeline object to get task data from
        fields (tuple): fields to request
        force (bool): create task without confirmation if missing

    Returns:
        (dict): shotgrid task data
    """
    if isinstance(obj, pipe.CPWork):
        return _work_to_task_data(obj, fields=fields)
    if isinstance(obj, pipe.CPOutputBase):
        return _output_to_task_data(obj, fields=fields)
    if isinstance(obj, pipe.CPWorkDir):
        return _find_task_data(
            task=obj.task, entity=obj.entity, fields=fields, force=force)
    raise ValueError(object)


def to_task_id(obj):
    """Obtain task id for the given pipe object.

    Args:
        obj (any): pipeline object to get task data from

    Returns:
        (int): task id
    """
    return to_task_data(obj)['id']


def _work_to_task_data(work, fields=()):
    """Obtain task data from the given work file.

    Args:
        work (CPWork): work file to read
        fields (tuple): fields to request

    Returns:
        (dict): shotgrid task data
    """
    return _find_task_data(
        task=work.task, entity=work.entity, fields=fields)
