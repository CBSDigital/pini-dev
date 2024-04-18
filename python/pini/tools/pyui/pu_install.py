"""Tools for managing the pyui install decorator.

This allows pyui metadata to be applied to function definitions which
are to be built into an interface.
"""

import logging


from . import cpnt

_LOGGER = logging.getLogger(__name__)


def install(
        label=None, icon=None, clear=(), browser=(), hide=(), choices=None):
    """Builds a decorator which allows metadata to be added to a function.

    Args:
        label (str): override function label
        icon (str): override path to function icon
        clear (tuple): args to apply clear button to
        browser (tuple|dict): args to apply browser to
        hide (tuple): args to hide from ui
        choices (dict): arg/opts data for option lists

    Returns:
        (fn): decorator
    """
    def _build_pyui_dec(func):
        _dec = cpnt.PUDef(
            func, label=label, icon=icon, clear=clear, browser=browser,
            hide=hide, choices=choices)
        return _dec
    return _build_pyui_dec
