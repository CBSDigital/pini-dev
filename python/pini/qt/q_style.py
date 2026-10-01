"""Tools for mimicing maya's palette outside maya."""

import os

from pini import dcc
from .q_mgr import QtGui, QtWidgets, Qt

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
HIGHLIGHTEDTEXT_COLOR = BASE_COLOR.lighter(int(SPREAD * 2))

_HOU_22_SS = """
* { font-size: 9pt; }

QWidget { background-color: #444444; color: #c8c8c8; }
QLabel { background: transparent; padding: 1px 0; }

/* inset panels */
QListView, QListWidget, QTreeView, QTableView, QTextEdit, QPlainTextEdit {
    background-color: #2b2b2b;
    border: 1px solid #1c1c1c;
    outline: 0;
    selection-background-color: #5285a6;
    selection-color: #ffffff; }
QListView::item { padding: 2px 4px; }
QListView::item:selected { background-color: #5285a6; }

/* inputs */
QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {
    background-color: #2b2b2b;
    border: 1px solid #1c1c1c;
    border-radius: 2px;
    padding: 2px; }
QLineEdit:focus, QComboBox:focus, QSpinBox:focus { border: 1px solid #5285a6; }
QComboBox::drop-down { border: none; width: 18px; }
QComboBox QAbstractItemView {
    background-color: #2b2b2b;
    border: 1px solid #1c1c1c;
    selection-background-color: #5285a6; }

/* buttons */
QPushButton {
    background-color: #5d5d5d;
    border: 1px solid #1c1c1c;
    border-radius: 2px;
    min-height: 18px; }
QPushButton:hover   { background-color: #707070; }
QPushButton:pressed { background-color: #484848; }
QPushButton:disabled { color: #808080; background-color: #4e4e4e; }

QToolButton {
    background: transparent;
    border: 1px solid transparent;
    border-radius: 2px;
    padding: 3px; }
QToolButton:hover { border: 1px solid #1c1c1c; background-color: #555555; }

/* tabs */
QTabWidget::pane {
    border: 1px solid #1c1c1c;
    background-color: #444444;
    top: -1px;
    padding: 6px; }
QTabBar::tab {
    background: #3a3a3a;
    border: 1px solid #1c1c1c;
    border-bottom: none;
    padding: 5px 15px;
    margin-right: 2px; }
QTabBar::tab:selected { background: #5d5d5d; color: #ffffff; }

QScrollBar:vertical { background: #2b2b2b; width: 12px; margin: 0; }
QScrollBar::handle:vertical {
    background: #5d5d5d;
    border-radius: 3px;
    min-height: 24px;
    margin: 2px; }
QScrollBar::add-line, QScrollBar::sub-line { height: 0; width: 0; }

QMessageBox, QDialog { border: 1px solid #1c1c1c; }
QMessageBox QLabel { padding: 6px; }
QToolTip {
    background-color: #2b2b2b;
    color: #ddd;
    border: 1px solid #1c1c1c;
    padding: 3px; }
"""


def apply_base_style(widget):
    """Apply base style for current env.

    Some dccs have odd styles (eg. hou-22) and need to be adjusted.

    Args:
        widget (QWidget): widget to adjust
    """
    _ver = dcc.to_version()
    _ss = None
    if dcc.NAME == 'hou' and _ver[0] >= 22:
        _ss = _HOU_22_SS

    if _ss:
        widget.setStyleSheet(_ss)
        _fix_lyt_margins(widget)


def _fix_lyt_margins(widget, spacing=2, margin=2):
    """Fix margins + spacing in child layouts.

    Args:
        widget (QWidget): parent widget
        spacing (int): apply spacing
        margin (int): apply margins
    """
    for _layout in widget.findChildren(QtWidgets.QLayout):
        _layout.setSpacing(spacing)
        _layout.setContentsMargins(margin, margin, margin, margin)


def set_dark_style(mode='helper'):
    """Set qt to dark style.

    Args:
        mode (str): how to apply dark style
            helper - use pini helper palette (works for CListView)
            qdarkstyle - use qdarkstyle module
            maya - use maya palette (missing some colours)
    """
    if mode == 'helper':
        _apply_helper_palette()
    elif mode == 'qdarkstyle':
        _apply_qdarkstyle_ss()
    elif mode == 'maya':
        _apply_maya_palette()
    else:
        raise ValueError(mode)


def _apply_helper_palette():
    """Apply pini helper palette."""
    from pini import qt

    _app = qt.get_application()
    _app.setStyle("Fusion")

    _pal = QtGui.QPalette()
    _pal.setColor(QtGui.QPalette.AlternateBase, QtGui.QColor(53, 53, 53))
    _pal.setColor(QtGui.QPalette.Base, QtGui.QColor(25, 25, 25))
    _pal.setColor(QtGui.QPalette.BrightText, Qt.red)
    _pal.setColor(QtGui.QPalette.Button, QtGui.QColor(53, 53, 53))
    _pal.setColor(QtGui.QPalette.ButtonText, Qt.white)
    _pal.setColor(QtGui.QPalette.Highlight, QtGui.QColor(42, 130, 218))
    _pal.setColor(QtGui.QPalette.HighlightedText, Qt.black)
    _pal.setColor(QtGui.QPalette.Link, QtGui.QColor(42, 130, 218))
    _pal.setColor(QtGui.QPalette.Text, Qt.white)
    _pal.setColor(QtGui.QPalette.ToolTipBase, Qt.black)
    _pal.setColor(QtGui.QPalette.ToolTipText, Qt.white)
    _pal.setColor(QtGui.QPalette.Window, QtGui.QColor(53, 53, 53))
    _pal.setColor(QtGui.QPalette.WindowText, Qt.white)
    _app.setPalette(_pal)


def _apply_qdarkstyle_ss():
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


def _apply_maya_palette():
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
