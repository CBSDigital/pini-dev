"""General tools for pyui module."""

import sys

from pini.utils import single, apply_filter


def find_ui(match=None):
    """Find a pyui interface.

    Args:
        match (str): match by name

    Returns:
        (PUBaseUi): matching interface
    """
    _uis = sys.PYUI_INTERFACES

    if not match and len(_uis) == 1:
        return single(_uis.values())

    _filter_matches = apply_filter(_uis.keys(), match)
    if len(_filter_matches) == 1:
        return _uis[single(_filter_matches)]

    raise ValueError(match)
