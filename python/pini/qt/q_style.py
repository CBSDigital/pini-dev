"""Tools for mimicing maya's palette outside maya."""

import os

from .q_mgr import QtGui, QtWidgets

HIGHLIGHT_COLOR = QtGui.QColor(103, 141, 178)
BRIGHTNESS_SPREAD = 2.5

BRIGHT_COLOR = QtGui.QColor(200, 200, 200)
LIGHT_COLOR = QtGui.QColor(100, 100, 100)
DARK_COLOR = QtGui.QColor(42, 42, 42)
MID_COLOR = QtGui.QColor(68, 68, 68)
MID_LIGHT_COLOR = QtGui.QColor(84, 84, 84)
SHADOW_COLOR = QtGui.QColor(21, 21, 21)

BASE_COLOR = MID_COLOR
TEXT_COLOR = BRIGHT_COLOR
DISABLED_BUTTON_COLOR = QtGui.QColor(78, 78, 78)
DISABLED_TEXT_COLOR = QtGui.QColor(128, 128, 128)
ALTERNATE_BASE_COLOR = QtGui.QColor(46, 46, 46)

SPREAD = 100 * BRIGHTNESS_SPREAD
HIGHLIGHTEDTEXT_COLOR = BASE_COLOR.lighter(int(SPREAD*2))


def set_dark_style():
    """Set dark style stylesheet."""
    from pini import qt

    # Safe import qdarkstyle - importing qtpy supresses at PyQt5 warning (?)
    # pylint: disable=unused-import,import-error
    _name = qt.QtWidgets.__name__.split('.')[0]
    os.environ['QT_API'] = _name
    import qdarkstyle
    import qtpy

    _app = qt.get_application()
    _app.setStyleSheet(qdarkstyle.load_stylesheet())


def set_maya_palette():
    """Apply maya palette.

    This allows interfaces outside maya to use the same colouring.
    """
    _base_palette = QtGui.QPalette()

    _base_palette.setBrush(
        QtGui.QPalette.Window, QtGui.QBrush(MID_COLOR))
    _base_palette.setBrush(
        QtGui.QPalette.WindowText, QtGui.QBrush(TEXT_COLOR))
    _base_palette.setBrush(
        QtGui.QPalette.Foreground, QtGui.QBrush(BRIGHT_COLOR))
    _base_palette.setBrush(
        QtGui.QPalette.Base, QtGui.QBrush(DARK_COLOR))
    _base_palette.setBrush(
        QtGui.QPalette.AlternateBase, QtGui.QBrush(ALTERNATE_BASE_COLOR))
    _base_palette.setBrush(
        QtGui.QPalette.ToolTipBase, QtGui.QBrush(BASE_COLOR))
    _base_palette.setBrush(
        QtGui.QPalette.ToolTipText, QtGui.QBrush(TEXT_COLOR))

    _base_palette.setBrush(
        QtGui.QPalette.Text, QtGui.QBrush(TEXT_COLOR))
    _base_palette.setBrush(
        QtGui.QPalette.Disabled, QtGui.QPalette.Text,
        QtGui.QBrush(DISABLED_TEXT_COLOR))

    _base_palette.setBrush(
        QtGui.QPalette.Button, QtGui.QBrush(LIGHT_COLOR))
    _base_palette.setBrush(
        QtGui.QPalette.Disabled, QtGui.QPalette.Button,
        QtGui.QBrush(DISABLED_BUTTON_COLOR))
    _base_palette.setBrush(
        QtGui.QPalette.ButtonText, QtGui.QBrush(TEXT_COLOR))
    _base_palette.setBrush(
        QtGui.QPalette.Disabled, QtGui.QPalette.ButtonText,
        QtGui.QBrush(DISABLED_TEXT_COLOR))
    _base_palette.setBrush(
        QtGui.QPalette.BrightText, QtGui.QBrush(TEXT_COLOR))
    _base_palette.setBrush(
        QtGui.QPalette.Disabled, QtGui.QPalette.BrightText,
        QtGui.QBrush(DISABLED_TEXT_COLOR))

    _base_palette.setBrush(
        QtGui.QPalette.Light, QtGui.QBrush(LIGHT_COLOR))
    _base_palette.setBrush(
        QtGui.QPalette.Midlight, QtGui.QBrush(MID_LIGHT_COLOR))
    _base_palette.setBrush(
        QtGui.QPalette.Mid, QtGui.QBrush(MID_COLOR))
    _base_palette.setBrush(
        QtGui.QPalette.Dark, QtGui.QBrush(DARK_COLOR))
    _base_palette.setBrush(
        QtGui.QPalette.Shadow, QtGui.QBrush(SHADOW_COLOR))

    _base_palette.setBrush(
        QtGui.QPalette.Highlight, QtGui.QBrush(HIGHLIGHT_COLOR))
    _base_palette.setBrush(
        QtGui.QPalette.HighlightedText, QtGui.QBrush(HIGHLIGHTEDTEXT_COLOR))

    # Setup additional palettes for QTabBar and QTabWidget to look more like
    # maya.
    _tab_palette = QtGui.QPalette(_base_palette)
    _tab_palette.setBrush(QtGui.QPalette.Window, QtGui.QBrush(LIGHT_COLOR))
    _tab_palette.setBrush(QtGui.QPalette.Button, QtGui.QBrush(MID_COLOR))

    _widget_palettes = {}
    _widget_palettes["QTabBar"] = _tab_palette
    _widget_palettes["QTabWidget"] = _tab_palette

    QtWidgets.QApplication.setStyle("Plastique")
    QtWidgets.QApplication.setPalette(_base_palette)
    for _name, _palette in _widget_palettes.items():
        QtWidgets.QApplication.setPalette(_palette, _name)

    return _base_palette
