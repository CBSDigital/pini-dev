"""General tools relating to work directories."""

import logging

from pini import dcc, pipe

_LOGGER = logging.getLogger(__name__)

_TASK_MAP = {
    'prev': 'previs',
    'previz': 'previs',

    'lay': 'layout',
    'lyt': 'layout',

    'animation': 'anim',
    'ani': 'anim',
    'anm': 'anim',
    'mod': 'model',
    'surf': 'lookdev',
    'mat': 'lookdev',
    'lgt': 'lighting',
    'trk': 'tracking',

    'ani/rig': 'rig',
    'lgt/mod': 'lighting',
    'lgt/surf': 'lookdev',
}


def cur_task(fmt='local'):
    """Obtain current task name.

    Args:
        fmt (str): task format
            local - use local task name
            pini - use standardised pini name (eg. mod -> model)

    Returns:
        (str): current task
    """
    _work_dir = cur_work_dir()
    _task = _work_dir.task if _work_dir else None
    _step = _work_dir.step if _work_dir else None

    if fmt == 'full':
        if not _work_dir:
            return None
        if _step:
            return f'{_step}/{_task}'
        return _work_dir.task

    return map_task(_task, step=_step, fmt=fmt)


def cur_work_dir(entity=None):
    """Obtain current work dir.

    Args:
        entity (CPEntity): force parent entity (to facilitate caching)

    Returns:
        (CPWorkDir): current work dir
    """
    return to_work_dir(dcc.cur_file(), entity=entity)


def map_task(task, step=None, fmt='pini'):
    """Map task name.

    Args:
        task (str): task name to map
        step (str): step name to map - this can be used if the task is not
            descriptive, eg. dev
        fmt (str): task format
            local - use local task name (ie. does nothing)
            pini - use standardised pini name (eg. mod -> model)

    Returns:
        (str): mapped task name
    """

    if fmt == 'local':
        _task = task
    elif fmt == 'pini':
        _task = (
            _TASK_MAP.get(f'{step}/{task}') or
            _TASK_MAP.get(step) or
            _TASK_MAP.get(task) or
            step or
            task)
    else:
        raise ValueError(fmt)
    return _task


def to_work_dir(path, entity=None, catch=True):
    """Build a work dir object from the given path.

    Args:
        path (str): path to convert to work dir
        entity (CPEntity): force parent entity (to facilitate caching)
        catch (bool): no error if fail to create work dir

    Returns:
        (CPWorkDir|None): work dir (if any)
    """
    try:
        return pipe.CPWorkDir(path, entity=entity)
    except ValueError as _exc:
        if catch:
            return None
        raise _exc
