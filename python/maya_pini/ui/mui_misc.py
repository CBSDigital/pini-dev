"""Tools for managing the maya ui."""

import inspect
import logging
import sys

import shiboken2

from maya import cmds, mel

from pini.utils import wrap_fn, single, apply_filter
from maya_pini.utils import to_parent

_LOGGER = logging.getLogger(__name__)


def add_menu_item(command, label, image=None, parent=None, name=None):
    """Add a menu item.

    Args:
        command (fn): menu item command
        label (str): menu item label
        image (str): path to menu item icon
        parent (str): parent menu (if not current)
        name (str): ui element name - replaces any existing
    """
    from maya_pini import ui

    _args = []
    if name:
        if cmds.menuItem(name, exists=True):
            cmds.deleteUI(name)
        _args.append(name)

    _kwargs = {}
    if parent:
        _parent = ui.obtain_menu(parent)
        _kwargs['parent'] = _parent

    _cmd = command
    if inspect.isfunction(_cmd):  # Force ignore args inserted by maya
        _cmd = wrap_fn(_cmd)

    cmds.menuItem(
        *_args, command=_cmd, label=label, image=image, tearOff=False,
        **_kwargs)


def clear_script_editor():
    """Clear script editor text."""
    _reporter = mel.eval('string $tmp = $gCommandReporter;')
    if not cmds.cmdScrollFieldReporter(_reporter, query=True, exists=True):
        _LOGGER.error('COULD NOT FIND SCRIPT EDITOR REPORTER %s', _reporter)
        return
    cmds.cmdScrollFieldReporter(_reporter, edit=True, clear=True)


def find_ctrl(type_, label):
    """Find a ui element/control.

    Args:
        type_ (str): control type (eg. a button/checkBox etc)
        label (str): match by label

    Returns:
        (str): control handle
    """
    _ctrls = []
    for _ctrl in (cmds.lsUI(controls=True) or []):

        _exists_func = {'button': cmds.button}[type_]
        if not _exists_func(_ctrl, exists=True):
            continue

        if label:
            _label = cmds.button(_ctrl, query=True, label=True)
            if label != _label:
                continue

        _ctrls.append(_ctrl)

    return single(_ctrls)


def find_menu(label):
    """Find a menu with the given label.

    Args:
        label (str): label to match

    Returns:
        (str): label ui element name
    """
    _menus = cmds.lsUI(menus=True) or []
    for _menu in _menus:
        if not cmds.menu(_menu, query=True, exists=True):
            continue
        _label = cmds.menu(_menu, query=True, label=True)
        if _label == label:
            return _menu

    return None


def find_window(filter_):
    """Find a window.

    Args:
        filter_ (str): apply name filter

    Returns:
        (str): window token
    """
    _wins = apply_filter(cmds.lsUI(windows=True), filter_)
    return single(_wins)


def get_active_cam():
    """Get camera from the active model panel.

    Returns:
        (str): camera transform
    """
    _cam = cmds.modelEditor(
        get_active_model_editor(), query=True, camera=True)
    if cmds.objectType(_cam) == 'camera':
        _cam = to_parent(_cam)
    return _cam


def get_active_model_editor():
    """Get model editor for the active viewport.

    Returns:
        (str): active model editor
    """
    _editors = []
    for _panel in cmds.lsUI(panels=True):
        if not cmds.modelPanel(_panel, query=True, exists=True):
            continue
        _editor = cmds.modelPanel(_panel, query=True, modelEditor=True)
        _editors.append(_editor)
    if len(_editors) == 1:
        return single(_editors)
    _editors = [_editor for _editor in _editors
                if cmds.modelEditor(_editor, query=True, activeView=True)]
    if len(_editors) == 1:
        return single(_editors)
    raise ValueError(
        'No active view found - try middle-mouse clicking the viewport')


def get_main_window():
    """Get main window element name.

    Returns:
        (str): main window name
    """
    return mel.eval('$s=$gMainWindow')


def get_main_window_ptr(fix_core=False):
    """Get pointer to maya main window.

    Args:
        fix_core (bool): fix bug where maya returns a QCoreApplication
            instance instead of a QApplication (can be unstable)

    Returns:
        (QDialog): main window pointer
    """
    from pini.qt import QtWidgets, QtCore

    _app = QtWidgets.QApplication.instance()

    # Fix QCoreApplication bug
    if fix_core and type(_app) is QtCore.QCoreApplication:  # pylint: disable=unidiomatic-typecheck
        if not hasattr(sys, 'PINI_WRAPPED_QT_CORE_APPLICATION'):
            _LOGGER.info('WRAPPING QCoreApplication')
            _ptr = shiboken2.getCppPointer(_app)[0]
            _app = shiboken2.wrapInstance(_ptr, QtWidgets.QApplication)
            sys.PINI_WRAPPED_QT_CORE_APPLICATION = _app
        else:
            _app = sys.PINI_WRAPPED_QT_CORE_APPLICATION

    if not isinstance(_app, QtWidgets.QApplication):
        return None

    # Find main window
    _widgets = _app.topLevelWidgets()
    for _widget in _widgets:
        if _widget.objectName() == 'MayaWindow':
            return _widget

    raise RuntimeError('Could not find MayaWindow instance')


def obtain_menu(label, replace=False):
    """Obtain a menu ui element by its label, creating it if needed.

    Args:
        label (str): element name
        replace (bool): replace any existing menu

    Returns:
        (str): ui element name
    """

    _menu = find_menu(label)
    if _menu:
        if replace:
            cmds.deleteUI(_menu)
        else:
            return _menu

    # Create if not found
    return cmds.menu(
        label+"_MENU", label=label, tearOff=True, parent=get_main_window())


def raise_attribute_editor():
    """Raise attribute editor.

    This can be used to force some expressions to update (eg. aiStandIn frame).
    """
    _ae = mel.eval('getUIComponentDockControl("Attribute Editor", false)')
    cmds.workspaceControl(_ae, edit=True, collapse=False)


def reset_window(filter_):
    """Reset a window's position.

    This can be used to retrieve a window which is offscreen.

    Args:
        filter_ (str): name filter
    """
    _win = find_window(filter_)
    cmds.window(_win, edit=True, topLeftCorner=(0, 0))
