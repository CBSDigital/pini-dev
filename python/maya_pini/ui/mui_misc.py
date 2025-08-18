"""Tools for managing the maya ui."""

import inspect
import logging
import sys

from maya import cmds, mel

from pini.utils import wrap_fn, single, apply_filter, EMPTY, cache_result
from maya_pini.utils import to_parent, to_node

_LOGGER = logging.getLogger(__name__)


def add_menu_divider(parent=None, name=None, insert_after=EMPTY, label=None):
    """Add a menu divider item.

    Args:
        parent (str): parent menu (if not current)
        name (str): ui element name - replaces any existing
        insert_after (str): insert after the given existing element
        label (str): label for divider

    Returns:
        (str): ui element id
    """
    return _build_menu_item(
        parent=parent, insert_after=insert_after, name=name, divider=True,
        label=label)


def add_menu_item(
        command, label, image=None, parent=None, name=None, insert_after=EMPTY):  # pylint: disable=unused-argument
    """Add a menu item.

    Args:
        command (fn): menu item command
        label (str): menu item label
        image (str): path to menu item icon
        parent (str): parent menu (if not current)
        name (str): ui element name - replaces any existing
        insert_after (str): insert after the given existing element

    Returns:
        (str): ui element id
    """
    _kwargs = locals()
    return _build_menu_item(**_kwargs)


def _build_menu_item(
        command=None, label=None, image=None, parent=None, name=None,
        insert_after=EMPTY, divider=False):
    """Add a menu item.

    Args:
        command (fn): menu item command
        label (str): menu item label
        image (str): path to menu item icon
        parent (str): parent menu (if not current)
        name (str): ui element name - replaces any existing
        insert_after (str): insert after the given existing element
        divider (bool): create element as divider

    Returns:
        (str): ui element id
    """
    _LOGGER.debug('BUILD MENU ITEM %s', name)
    from maya_pini import ui

    # Build args (name)
    _args = []
    if name:
        if cmds.menuItem(name, exists=True):
            cmds.deleteUI(name)
        _args.append(name)

    # Build kwargs (items which can't be None)
    _kwargs = {}
    if parent:
        if cmds.shelfButton(parent, query=True, exists=True):
            _parent = parent
        else:
            _parent = ui.obtain_menu(parent)
        _kwargs['parent'] = _parent
    if insert_after is not EMPTY:
        _kwargs['insertAfter'] = insert_after or ''
    if command:
        _cmd = command
        if inspect.isfunction(_cmd):  # Force ignore args inserted by maya
            _cmd = wrap_fn(_cmd)
        _kwargs['command'] = _cmd

    _LOGGER.debug(' - KWARGS %s', _kwargs)
    _result = cmds.menuItem(
        *_args, divider=divider, label=label, image=image,
        tearOff=False, **_kwargs)
    _LOGGER.debug(' - RESULT %s', _result)
    return _result


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
    _editor = get_active_model_editor()
    if not _editor:
        return None
    _cam = cmds.modelEditor(_editor, query=True, camera=True)
    if not cmds.objExists(_cam):
        _cam = to_node(_cam)
    if cmds.objectType(_cam) == 'camera':
        _cam = to_parent(_cam)
    return _cam


def get_active_model_editor(catch=True):
    """Get model editor for the active viewport.

    Args:
        catch (bool): no error if no active editor found

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
    _LOGGER.debug(' - EDITORS %s', _editors)
    if len(_editors) == 1:
        return single(_editors)
    if catch:
        return None
    raise ValueError(
        'No active view found - try middle-mouse clicking the viewport')


@cache_result
def get_main_window():
    """Get main window element name.

    Returns:
        (str): main window name
    """
    if cmds.about(batch=True):
        raise RuntimeError('Batch mode')
    return mel.eval('$s=$gMainWindow')


def get_main_window_ptr(fix_core=False):
    """Get pointer to maya main window.

    Args:
        fix_core (bool): fix bug where maya returns a QCoreApplication
            instance instead of a QApplication (can be unstable)

    Returns:
        (QDialog): main window pointer
    """
    from pini.qt import QtWidgets, QtCore, shiboken

    _app = QtWidgets.QApplication.instance()

    # Fix QCoreApplication bug
    if fix_core and type(_app) is QtCore.QCoreApplication:  # pylint: disable=unidiomatic-typecheck
        if not hasattr(sys, 'PINI_WRAPPED_QT_CORE_APPLICATION'):
            _LOGGER.info('WRAPPING QCoreApplication')
            _ptr = shiboken.getCppPointer(_app)[0]
            _app = shiboken.wrapInstance(_ptr, QtWidgets.QApplication)
            sys.PINI_WRAPPED_QT_CORE_APPLICATION = _app
        else:
            _app = sys.PINI_WRAPPED_QT_CORE_APPLICATION

    if not isinstance(_app, QtWidgets.QApplication):
        return None

    # Find main window
    _widgets = _app.topLevelWidgets()
    for _widget in _widgets:
        if isinstance(_widget, (QtWidgets.QSpacerItem, QtWidgets.QWidgetItem)):
            continue
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
        label + "_MENU", label=label, tearOff=True, parent=get_main_window())


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
