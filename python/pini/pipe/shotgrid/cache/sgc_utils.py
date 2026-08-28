"""General utilities for managing the shotgrid cache."""

import logging

from pini.utils import passes_filter

_LOGGER = logging.getLogger(__name__)


def passes_filters(elem, filter_attr='path', **kwargs):
    """Check whether the element passes the given attribute filters.

    eg. _elem = shotgrid.SGC.find_job('CGDev')
        assert _elem.name == 'CGDev'
        assert passes_filters(_elem, name='CGDev')

    Args:
        elem (SGCElem): element
        filter_attr (str): which attribute to apply filter_ arg to
            (eg. path/uid)

    Returns:
        (bool): whether the given element passes the given filters
    """
    from . import sgc_elems

    _kwargs = kwargs
    _LOGGER.debug('PASSES FILTERS %s %s', elem, _kwargs)

    # Apply filter
    _filter = _kwargs.pop('filter_', None)
    if _filter:
        _filterable_val = getattr(elem, filter_attr)
        if not passes_filter(_filterable_val, _filter):
            return False

    # Apply task
    _task = _kwargs.pop('task', None)
    if _task:
        if isinstance(_task, sgc_elems.SGCTask):
            _task_s = _task.name
        elif isinstance(_task, str):
            _task_s = _task
        else:
            raise TypeError(_task)
        _kwargs['task'] = _task_s

    # Apply simple attr filters
    for _attr, _val in _kwargs.items():
        if _val is None:
            continue
        _elem_val = getattr(elem, _attr)
        if _elem_val != _val:
            return False

    return True
