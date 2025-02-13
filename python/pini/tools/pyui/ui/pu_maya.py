"""Tools for managing pyui interfaces in maya."""

import collections
import logging
import sys
import types

from maya import cmds

from pini import icons, qt, refresh, testing
from pini.tools import pyui
from pini.utils import wrap_fn, copy_text, chain_fns, EMPTY

from maya_pini import ui

from . import pu_base, pu_utils
from ..cpnt import pu_choice_mgr

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
        return 'PYUI_' + self.mod.__name__.replace('.', '_')

    def init_ui(self):
        """Inititiate interface window."""
        _name = self.uid
        if cmds.window(_name, exists=True):
            cmds.deleteUI(_name, window=True)
        cmds.window(
            self.uid, title=self.title,
            iconName='Short Name', closeCommand=self.close_event,
            width=400, menuBar=True)

        self.scroll = self.uid + '_scroll'
        cmds.scrollLayout(self.scroll, childResizable=True)
        self.master = self.uid + '_master'
        cmds.columnLayout(self.master, adjustableColumn=1)

        super().init_ui()

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
        _row = self._add_arg_lyt(arg, height=self.arg_h)

        # Add label
        cmds.text(arg.label, align='left', statusBarMessage=arg.docs)

        # Add arg field
        _read_fn, _set_fn, _field = self._add_arg_field(arg)

        # Add extras
        if isinstance(arg.choices, pu_choice_mgr.PUChoiceMgr):
            cmds.iconTextButton(
                image1=icons.REFRESH, width=self.arg_h, height=self.arg_h,
                style='iconOnly', statusBarMessage='Reread options',
                command=wrap_fn(
                    _apply_update_opt_menu, mgr=arg.choices, field=_field))
        if arg.browser:
            cmds.iconTextButton(
                image1=icons.BROWSER, width=self.arg_h, height=self.arg_h,
                style='iconOnly', statusBarMessage='Launch browser',
                command=wrap_fn(
                    pu_utils.apply_browser_btn, mode=arg.browser_mode,
                    read_fn=_read_fn, set_fn=_set_fn))
        if arg.clear:
            cmds.iconTextButton(
                image1=icons.CLEAR, width=self.arg_h, height=self.arg_h,
                style='iconOnly', statusBarMessage='Clear text',
                command=wrap_fn(cmds.textField, _field, edit=True, text=''))
        if arg.selection:
            _type = None
            _tooltip = 'Get selection'
            if isinstance(arg.selection, str):
                _type = arg.selection
                _tooltip = 'Get selected ' + _type
            cmds.iconTextButton(
                image1=icons.SELECT, width=self.arg_h, height=self.arg_h,
                style='iconOnly', statusBarMessage=_tooltip,
                command=wrap_fn(_apply_selection, field=_field, type_=_type))

        cmds.setParent('..')

        return _read_fn, _set_fn, _field

    def _add_arg_lyt(self, arg, height):
        """Add build row layout for the given arg.

        Args:
            arg (PUArg): arg to add
            height (int): field height in pixels

        Returns:
            (str): row layout field
        """
        _label_w = arg.label_w or self.label_w
        _col_width = [(1, _label_w), (2, 1000)]
        _n_cols = 2
        for _tgl in [
                arg.clear, arg.browser, arg.selection,
                isinstance(arg.choices, pu_choice_mgr.PUChoiceMgr),
        ]:
            if _tgl:
                _n_cols += 1
                _col_width.append((_n_cols, height))

        return cmds.rowLayout(
            numberOfColumns=_n_cols, columnWidth=_col_width,
            width=100, adjustableColumn=2)

    def _add_arg_field(self, arg):
        """Build an arg field.

        Args:
            arg (PUArg): arg to add

        Returns:
            (tuple): read func, set func, field name
        """
        _set_fn = None
        _default = arg.default
        if _default is None or _default is EMPTY:
            _default = ''
        if arg.choices:
            if isinstance(
                    arg.choices, (tuple, list, set, collections.abc.Iterable)):
                _choices = arg.choices
                _select = _default
            elif isinstance(arg.choices, pu_choice_mgr.PUChoiceMgr):
                _choices = arg.choices.choices
                _select = arg.choices.default
            elif isinstance(arg.choices, types.FunctionType):
                _choices = arg.choices()
                _select = _default
            else:
                raise ValueError(arg.choices)
            _LOGGER.debug(' - CHOICES %s %s', _select, _choices)
            _opt_menu = ui.create_option_menu(options=_choices, select=_select)
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
        elif isinstance(_default, str) or _default is None:
            _LOGGER.debug('   - CREATE TEXTFIELD')
            _field = cmds.textField(text=_default)
            _read_fn = wrap_fn(cmds.textField, _field, query=True, text=True)
        else:
            raise ValueError(_default)
        _set_fn = _build_apply_fn(field=_field)

        return _read_fn, _set_fn, _field

    def finalize_def(self, def_):
        """Finalize function.

        Args:
            def_ (PUDef): function to finalize
        """
        assert isinstance(def_, pyui.PUDef)
        _LOGGER.debug(' - ADD EXECUTE %s', def_)

        _col = qt.to_col(def_.col or self.base_col)

        cmds.text(def_.uid + 'Spacer', label='', height=3)  # Spacer
        cmds.rowLayout(
            numberOfColumns=3, columnWidth3=(self.def_h, 75, self.def_h),
            adjustableColumn=2, columnAlign=(1, 'right'),
            columnAttach=[(1, 'left', 0), (2, 'both', 0), (3, 'right', 0)])

        cmds.iconTextButton(
            image1=def_.icon, width=self.def_h, height=self.def_h,
            style='iconOnly', command=def_.edit)

        # Add execute button
        _docs = def_.py_def.to_docs('Title')
        _exec = wrap_fn(self._execute_def, def_)
        _btn = cmds.button(
            label=def_.label, command=_exec, height=self.def_h,
            backgroundColor=_col.to_tuple(float), statusBarMessage=_docs)
        self._add_execute_ctx(button=_btn, def_=def_, exec_=_exec)

        # Add icon button
        _info = wrap_fn(
            qt.notify, def_.py_def.to_docstring(), icon=def_.icon,
            title=def_.label)
        cmds.iconTextButton(
            image1=pu_base.INFO_ICON, width=self.def_h, height=self.def_h,
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
        cmds.menuItem(divider=True)

        cmds.menuItem(
            'Lock button', parent=_menu,
            image=icons.LOCKED,
            command=wrap_fn(cmds.button, button, edit=True, enable=False))
        cmds.menuItem(
            'Refresh and execute', parent=_menu,
            image=icons.REFRESH,
            command=chain_fns(refresh.reload_libs, exec_))
        cmds.menuItem(
            'Execute in profile', parent=_menu,
            image=icons.find('High Voltage'),
            command=testing.profile(exec_))
        cmds.menuItem(
            'Reset settings', parent=_menu,
            image=icons.RESET,
            command=wrap_fn(self.reset_settings, def_=def_))

    def set_section(self, section):
        """Set current collapsable section.

        Args:
            section (PUSection): section to apply
        """
        super().set_section(section)

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
            'get': wrap_fn(
                cmds.frameLayout, _frame, query=True, collapse=True),
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
            _val = bool(val)
            cmds.checkBox(field, edit=True, value=_val)
        elif cmds.intField(field, query=True, exists=True):
            cmds.intField(field, edit=True, value=val)
        elif cmds.optionMenu(field, query=True, exists=True):
            ui.OptionMenu(field).set_val(val)
        elif cmds.frameLayout(field, query=True, exists=True):
            cmds.frameLayout(field, edit=True, collapse=val)
        else:
            _LOGGER.warning('FAILED TO APPLY VALUE %s %s', val, field)

    return _apply_val


def _apply_selection(field, type_):
    """Apply get current selection.

    Args:
        field (str): field to apply to
        type_ (str): apply node type filter
    """
    _LOGGER.info('APPLY SELECTION %s', type_)
    _kwargs = {}
    if type_:
        _kwargs['type'] = type_
    _sel = ' '.join(cmds.ls(selection=True, **_kwargs))
    _LOGGER.info(' - SEL %s', _sel)
    cmds.textField(field, edit=True, text=_sel)


def _apply_update_opt_menu(mgr, field):
    """Apply option menu update.

    Args:
        mgr (PUChoiceMgr): choice manager
        field (str): field to update
    """
    _LOGGER.info('APPLY OPT MENU UPDATE %s %s', mgr.choices, mgr.default)
    _menu = ui.OptionMenu(field)
    _menu.set_opts(mgr.choices)
    _menu.set_val(mgr.default)
