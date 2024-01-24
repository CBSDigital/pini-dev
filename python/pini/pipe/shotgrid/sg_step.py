"""Tools for managing shotgrid pipeline steps."""

import logging

import six

from pini.utils import single

from . import sg_handler, sg_utils

_LOGGER = logging.getLogger(__name__)
_STEP_FIELDS = ['entity_type', 'code', 'short_name', 'department']


class MissingPipelineStep(RuntimeError):
    """Raised when a step doesn't match the available shotgrid steps."""


def find_steps(fmt='dict', only_3d=False):
    """Find steps data from shotgrid.

    Args:
        fmt (str): result format (
            dict - full data dict list
            name - list of names
        only_3d (bool): return only 3d steps

    Returns:
        (list): steps data
    """
    _steps = _read_steps_data()
    if only_3d:
        _steps = [_step for _step in _steps
                  if _step['department'] and
                  _step['department']['name'] == '3D']

    if fmt == 'dict':
        _result = _steps
    elif fmt == 'name':
        _result = [_step['short_name'] for _step in _steps]
    else:
        raise NotImplementedError(fmt)

    return _result


@sg_utils.sg_cache_result
def _read_steps_data():
    """Read all pipeline steps data.

    Returns:
        (dict): steps data
    """
    return sg_handler.find('Step', fields=_STEP_FIELDS)


@sg_utils.sg_cache_result
def to_step_data(match, entity_type=None):
    """Obtain step data for the given task and entity.

    Args:
        match (int/str): step id/name
        entity_type (str): Asset/Shot

    Returns:
        (dict): shotgrid step data
    """
    _LOGGER.debug('TO STEP DATA %s %s', match, entity_type)

    _data = _read_steps_data()
    if entity_type:
        _data = [_item for _item in _data
                 if _item['entity_type'] == entity_type]

    if isinstance(match, int):
        return single(_item for _item in _data if _item['id'] == match)

    if isinstance(match, six.string_types):
        return single(_item for _item in _data if _item['code'] == match)

    raise ValueError(match)
