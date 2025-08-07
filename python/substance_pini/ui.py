"""Interface tools for substance."""

import logging

import substance_painter

from pini import qt
from pini.qt import QtWidgets
from pini.utils import single

_LOGGER = logging.getLogger(__name__)


def delete_menu(name):
    """Delete any menu with the given name.

    Args:
        name (str): name of menu to delete
    """
    _menu = obt_menu(name, create=False)
    if _menu:
        _menu.deleteLater()
        substance_painter.ui.delete_ui_element(_menu)


def obt_menu(name, flush=False, create=True):
    """Find a menu, creating it if needed.

    Args:
        name (str): menu name
        flush (bool): remove existing actions
        create (bool): create menu if it doesn't exist

    Returns:
        (CMenu): menu
    """
    _menu = single([
        _widget for _widget in qt.find_widget_children(
            to_main_window(), class_=QtWidgets.QMenu)
        if _widget.title() == name], catch=True)
    if flush and _menu:
        substance_painter.ui.delete_ui_element(_menu)
        _menu = None

    if create and not _menu:
        _LOGGER.debug('CREATE MENU %s', name)
        _menu = qt.CMenu(name, parent=to_main_window())
        substance_painter.ui.add_menu(_menu)

    return _menu


def to_main_window():
    """Obtain main window pointer.

    Returns:
        (QMainWindow): main window
    """
    return substance_painter.ui.get_main_window()
