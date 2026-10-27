"""General tools for pyui module."""

import operator
import sys

from pini.utils import single, apply_filter


def find_ui(match=None, filter_=None):
    """Find a pyui interface.

    Args:
        match (str): match by name
        filter_ (str): apply interface title filter

    Returns:
        (PUBaseUi): matching interface
    """
    _uis = find_uis(filter_=filter_)

    if not match and len(_uis) == 1:
        return single(_uis)

    _matches = [
        _ui for _ui in _uis
        if match in (_ui.mod.__name__, _ui.py_file.path)]
    if len(_matches) == 1:
        return single(_matches)

    _filter_matches = apply_filter(
        _uis, match, key=operator.attrgetter('title'))
    if len(_filter_matches) == 1:
        return single(_filter_matches)

    raise ValueError(match)


def find_uis(filter_=None):
    """Find pyui interfaces.

    Args:
        filter_ (str): apply interface title filter

    Returns:
        (PUBaseUi list): interfaces
    """
    _uis = list(sys.PYUI_INTERFACES.values())
    if filter_:
        _uis = apply_filter(_uis, filter_, key=operator.attrgetter('title'))

    return _uis
