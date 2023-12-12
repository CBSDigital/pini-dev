"""Tools for managing shotgrid pipeline steps."""

import logging

from pini.utils import cache_result


_LOGGER = logging.getLogger(__name__)


class MissingPipelineStep(RuntimeError):
    """Raised when a step doesn't match the available shotgrid steps."""


@cache_result
def to_step_data(step, entity_type='Shot'):
    """Obtain step data for the given task and entity.

    Args:
        step (str): step name
        entity_type (str): Asset/Shot

    Returns:
        (dict): shotgrid step data
    """
    from pini.pipe import shotgrid

    _LOGGER.debug('TO STEP DATA %s %s', step, entity_type)
    _sg = shotgrid.to_handler()

    _filters = [
        ('code', 'is', step),
        ('entity_type', 'is', entity_type),
    ]
    _fields = ['entity_type', 'code']
    _LOGGER.debug(' - FILTERS %s', _filters)
    _data = _sg.find_one('Step', filters=_filters, fields=_fields)
    if not _data:
        raise MissingPipelineStep(
            'No {}/{} pipeline step found'.format(entity_type, step))

    return _data
