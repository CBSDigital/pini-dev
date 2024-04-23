"""Tools for managing pyui interfaces in maya."""

import logging
import sys

import six

from maya import cmds

from pini import icons, qt, refresh, pipe
from pini.tools import pyui
from pini.utils import (
    to_nice, wrap_fn, copy_text, chain_fns, EMPTY, Path, abs_path)

from maya_pini import ui

from . import pu_base

_LOGGER = logging.getLogger(__name__)


class PUMayaUi(pu_base.PUBaseUi):
    """Maya interface built from a python file."""

    scroll = None
    master = None

    @property
    def uid(self):
        """Obtain uid for this interface.

        Returns:
            (str): unique indentifier
        """
        return 'PYUI_'+self.mod.__name__.replace('.', '_')

    def init_ui(self):
        """Inititiate interface window."""
        _name = self.uid
        if cmds.window(_name, exists=True):
            cmds.deleteUI(_name, window=True)
        cmds.window(
            self.uid, title=self.title,
            iconName='Short Name', closeCommand=self.close_event,
            width=400, menuBar=True)

        self.scroll = self.uid+'_scroll'
        cmds.scrollLayout(self.scroll, childResizable=True)
        self.master = self.uid+'_master'
        cmds.columnLayout(self.master, adjustableColumn=1)

        super(PUMayaUi, self).init_ui()

    def add_menu(self, name):
        """Add menu to interface.

        Args:
            name (str): menu name
        """
        return cmds.menu(label=name)

    def add_menu_item(self, parent, label, command=None, image=None):
        """Add menu item to the given menu.

        Args:
            parent (str): menu to add item to
            label (str): item label
            command (fn): item callback
            image (str): path to item image
        """
        _kwargs = {}
        if image:
            _kwargs['image'] = image
        if command:
            _kwargs['command'] = command
        return cmds.menuItem(parent=parent, label=label, **_kwargs)

    def add_menu_separator(self, parent):
        """Add a separator item to the given menu bar.

        Args:
            parent (str): menu to add item to
        """
        return cmds.menuItem(parent=parent, divider=True)

    def add_separator(self):
        """Add separator."""
        cmds.separator(style='out', height=10, horizontal=True)

    def init_def(self, def_):
        """Initiate new function.

        Args:
            def_ (PUDef): function to initiate
        """

    def add_arg(self, arg):
        """Add argument.

        Args:
            arg (PUArg): arg to add
        """
        _LOGGER.debug(
            ' - ADD ARG %s default=%s browser=%s choices=%s',
            arg, arg.default, arg.browser, arg.choices)

        # Build row layout
        _height = 20
        _col_width = [(1, arg.label_w), (2, 1000)]
        _n_cols = 2
        if arg.clear:
            _n_cols += 1
            _col_width.append((_n_cols, _height))
        if arg.browser:
            _n_cols += 1
            _col_width.append((_n_cols, _height))
        _row = cmds.rowLayout(
            numberOfColumns=_n_cols,
            columnWidth=_col_width,
            width=100,
            adjustableColumn=2)

        # Add label
        _label = to_nice(arg.name).capitalize()
        cmds.text(_label, align='left')

        # Add arg field
        _set_fn = None
        _default = arg.default
        if _default is None or _default is EMPTY:
            _default = ''
        if arg.choices:
            _opt_menu = ui.create_option_menu(arg.choices)
            _field = _opt_menu.field
            _read_fn = _opt_menu.get_val
        elif isinstance(_default, float):
            _field = cmds.floatField(value=_default)
            _read_fn = wrap_fn(cmds.floatField, _field, query=True, value=True)
        elif isinstance(_default, bool):
            _LOGGER.debug('   - CREATE CHECKBOX')
            _field = cmds.checkBox(label='', value=_default)
            _read_fn = wrap_fn(cmds.checkBox, _field, query=True, value=True)
        elif isinstance(_default, int):
            _field = cmds.intField(value=_default)
            _read_fn = wrap_fn(cmds.intField, _field, query=True, value=True)
        elif isinstance(_default, six.string_types) or _default is None:
            _LOGGER.debug('   - CREATE TEXTFIELD')
            _field = cmds.textField(text=_default)
            _read_fn = wrap_fn(cmds.textField, _field, query=True, text=True)
        else:
            raise ValueError(_default)
        _set_fn = _build_apply_fn(field=_field)

        # Add extras
        if arg.browser:
            _mode = None if arg.browser is True else arg.browser
            cmds.iconTextButton(
                image1=icons.BROWSER, width=_height, height=_height,
                style='iconOnly',
                command=wrap_fn(_apply_browser, mode=_mode, field=_field))
        if arg.clear:
            cmds.iconTextButton(
                image1=icons.CLEAR, width=_height, height=_height,
                style='iconOnly',
                command=wrap_fn(cmds.textField, _field, edit=True, text=''))

        cmds.setParent('..')

        return _read_fn, _set_fn, _field

    def finalize_def(self, def_):
        """Finalize function.

        Args:
            def_ (PUDef): function to finalize
        """
        assert isinstance(def_, pyui.PUDef)
        _LOGGER.debug(' - ADD EXECUTE %s', def_)

        _size = 35
        _col = qt.to_col(def_.col or self.base_col)

        cmds.text('', height=3)  # Spacer
        cmds.rowLayout(
            numberOfColumns=3, columnWidth3=(_size, 75, _size),
            adjustableColumn=2, columnAlign=(1, 'right'),
            columnAttach=[(1, 'left', 0), (2, 'both', 0), (3, 'right', 0)])

        cmds.iconTextButton(
            image1=def_.icon, width=_size, height=_size,
            style='iconOnly', command=def_.py_def.edit)

        # Add execute button
        _exec = wrap_fn(self._execute_def, def_)
        _btn = cmds.button(
            label=def_.label, command=_exec, height=_size,
            backgroundColor=_col.to_tuple(float))
        self._add_execute_ctx(button=_btn, def_=def_, exec_=_exec)

        # Add icon button
        _info = wrap_fn(
            qt.notify, def_.py_def.to_docs(), icon=def_.icon,
            title=def_.label)
        cmds.iconTextButton(
            image1=pu_base.INFO_ICON, width=_size, height=_size,
            style='iconOnly', command=_info)

        cmds.setParent('..')

    def _add_execute_ctx(self, button, def_, exec_):
        """Add right-click options to execute button.

        Args:
            button (str): button to add options to
            def_ (PUDef): function being added
            exec_ (fn): execute function
        """
        _menu = cmds.popupMenu(parent=button)

        _cmd = '\n'.join([
            'import {} as _mod',
            'print(_mod.{})',
        ]).format(self.py_file.to_module().__name__, def_.name)
        cmds.menuItem(
            'Copy import statement', parent=_menu,
            image=icons.COPY,
            command=wrap_fn(copy_text, _cmd))

        cmds.menuItem(
            'Lock button', parent=_menu,
            image=icons.LOCKED,
            command=wrap_fn(cmds.button, button, edit=True, enable=False))
        cmds.menuItem(
            'Refresh and execute', parent=_menu,
            image=icons.REFRESH,
            command=chain_fns(refresh.reload_libs, exec_))
        cmds.menuItem(
            'Reset settings', parent=_menu,
            image=icons.RESET,
            command=wrap_fn(self.reset_settings, def_=def_))

    def set_section(self, section):
        """Set current collapsable section.

        Args:
            section (PUSection): section to apply
        """
        super(PUMayaUi, self).set_section(section)

        _resize = wrap_fn(
            cmds.evalDeferred, self._resize_to_fit_children,
            lowestPriority=True)
        _frame = cmds.frameLayout(
            collapsable=True, label=section.name, collapse=section.collapse,
            parent=self.master,
            collapseCommand=_resize,
            expandCommand=_resize,
            backgroundColor=qt.to_col(self.section_col).to_tuple(float))
        _LOGGER.debug(' - SECTION %s', _frame)
        cmds.columnLayout(parent=_frame, adjustableColumn=1)
        self.callbacks['sections'][section.name] = {
            'get': wrap_fn(cmds.frameLayout, _frame, query=True, collapse=True),
            'set': _build_apply_fn(_frame)}

    def collapse_all(self):
        """Collapse all sections."""
        _callbacks = sys.PYUI_CALLBACKS[self.mod.__name__]
        for _sect_name, _sect_callbacks in _callbacks['sections'].items():
            _sect_callbacks['set'](True)
        cmds.evalDeferred(self._resize_to_fit_children)

    def finalize_ui(self, show=True):
        """Finalize building interface.

        Args:
            show (bool): show interface
        """
        cmds.setParent('..')
        if show:
            cmds.showWindow(self.uid)
        self._resize_to_fit_children()

    def _resize_to_fit_children(self):
        """Resize interface to fit child elements."""
        cmds.refresh()
        _col_h = cmds.columnLayout(self.master, query=True, height=True)
        _height = _col_h + 25
        _LOGGER.debug(' - TO FIT CHILDREN RESIZE %s %d', self.uid, _height)
        cmds.window(self.uid, edit=True, height=_height)

    def _safe_exec_launch(self, launch):
        """Execute launch function.

        Maya becomes unstable if a ui is launched from the thread of an
        existing ui, so the launch function is wrapped in an evalDeferred.

        Args:
            launch (fn): launch function
        """
        cmds.evalDeferred(launch)

    def close(self):
        """Close this interface."""
        cmds.deleteUI(self.uid)


def _build_apply_fn(field):
    """Build function which applies data to the given field.

    Args:
        field (str): field to apply data to

    Returns:
        (fn): function to apply data to field
    """

    def _apply_val(val):
        _LOGGER.debug('APPLY VAL %s %s', field, val)
        if cmds.textField(field, query=True, exists=True):
            cmds.textField(field, edit=True, text=val)
        elif cmds.checkBox(field, query=True, exists=True):
            cmds.checkBox(field, edit=True, value=val)
        elif cmds.intField(field, query=True, exists=True):
            cmds.intField(field, edit=True, value=val)
        elif cmds.optionMenu(field, query=True, exists=True):
            ui.OptionMenu(field).set_val(val)
        elif cmds.frameLayout(field, query=True, exists=True):
            cmds.frameLayout(field, edit=True, collapse=val)
        else:
            raise ValueError(val, field)

    return _apply_val


def _apply_browser(field, mode):
    """Launch browser and apply its result to the given field.

    Args:
        field (str): field to apply result to
        mode (str): browser mode (eg. ExistingFile)
    """
    _LOGGER.debug('BROWSER %s', mode)

    # Determine root
    _root = None
    _cur_path = cmds.textField(field, query=True, text=True)
    if _cur_path:
        _cur_path = Path(abs_path(_cur_path))
        _LOGGER.debug(' - CUR PATH %s', _cur_path.path)
        if _cur_path.exists():
            if not _cur_path.is_dir():
                _cur_path = _cur_path.to_dir()
            _root = _cur_path
    for _root in [pipe.cur_work_dir(), pipe.cur_entity(), pipe.cur_job()]:
        if _root:
            break
    _LOGGER.info(' - ROOT %s', _root)

    _result = qt.file_browser(mode=mode, root=_root)
    _LOGGER.debug(' - RESULT %s', _result)
    cmds.textField(field, edit=True, text=_result.path)