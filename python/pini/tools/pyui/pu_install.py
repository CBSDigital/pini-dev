"""Tools for managing the pyui install decorator.

This allows pyui metadata to be applied to function definitions which
are to be built into an interface.
"""

import logging


from . import cpnt

_LOGGER = logging.getLogger(__name__)


def install(
        label=None, icon=None, clear=(), browser=(), hide=(), choices=None,
        label_w=None, selection=()):
    """Builds a decorator which allows metadata to be added to a function.

    Args:
        label (str): override function label
        icon (str): override path to function icon
        clear (tuple): args to apply clear button to
        browser (tuple|dict): args to apply browser to
            tuple - apply browser in ExistingFile mode to these args
            dict - apply browser in given mode to these args
        hide (tuple): args to hide from ui
        choices (dict): arg/opts data for option lists
        label_w (int): override label width (in pixels)
        selection (tuple|dict): args to apply get selected button to
            tuple - apply get selected node to these args
            dict - apply get selected node of given type to these args

    Returns:
        (fn): decorator
    """
    def _build_pyui_dec(func):
        _dec = cpnt.PUDef(
            func, label=label, icon=icon, clear=clear, browser=browser,
            hide=hide, choices=choices, label_w=label_w, selection=selection)
        return _dec
    return _build_pyui_dec
