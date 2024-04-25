"""Tools for managing the pyui interface base class."""

# pylint: disable=too-many-instance-attributes

import inspect
import logging
import sys

from pini import icons, qt
from pini.tools import error
from pini.utils import (
    PyFile, str_to_seed, wrap_fn, six_reload, abs_path, last,
    copy_text, HOME)

from .. import cpnt

_LOGGER = logging.getLogger(__name__)

# Setup callback cache in sys module to survive rebuild
if not hasattr(sys, 'PYUI_CALLBACKS'):
    sys.PYUI_CALLBACKS = {}
CALLBACKS_CACHE = sys.PYUI_CALLBACKS

_SETTING_ROOT = HOME.to_subdir('.pini/settings/pyui')
_NICE_COLS = [
    'red', 'tomato', 'coral', 'orangered', 'sandybrown', 'darkorange',
    'orange', 'gold', 'yellow', 'greenyellow', 'chartreuse', 'lawngreen',
    'lime', 'springgreen', 'mediumspringgreen', 'aqua', 'cyan', 'deepskyblue',
    'dodgerblue', 'cornflowerblue', 'blue', 'mediumslateblue', 'fuchsia',
    'magenta', 'deeppink', 'hotpink']
INFO_ICON = icons.find('Information')


class PUBaseUi(object):
    """Base class for all pyui interfaces."""

    label_w = 70

    _mod = None
    _cur_section = None

    def __init__(
            self, py_file, title=None, base_col='RoyalBlue',
            load_settings=True):
        """Constructor.

        Args:
            py_file (str): path to py file to build into interface
            title (str): override interface title
            base_col (str|QColor): override interface base colour
            load_settings (bool): load settings on launch
        """
        self.py_file = cpnt.PUFile(py_file)
        self.name = self.mod.__name__
        self.settings_file = _SETTING_ROOT.to_file(self.name+'.pkl')

        self.title = title
        if not self.title and hasattr(self.mod, 'PYUI_TITLE'):
            self.title = self.mod.PYUI_TITLE
        if not self.title:
            self.title = self.name

        self.base_col = base_col
        if not self.base_col and hasattr(self.mod, 'PYUI_COL'):
            self.base_col = self.mod.PYUI_COL
        if not self.base_col:
            _rand = str_to_seed(self.name)
            self.base_col = _rand.choice(_NICE_COLS)
        assert self.base_col

        self.section_col = qt.to_col(self.base_col).blacken(0.5)

        self.callbacks = {'defs': {}, 'sections': {}}

        self.build_ui(load_settings=load_settings)

    @property
    def mod(self):
        """Obtain module for this python file.

        Returns:
            (mod): python module
        """
        if not self._mod:
            self._mod = self.py_file.to_module()
        return self._mod

    def build_ui(self, load_settings=True):
        """Build interface.

        Args:
            load_settings (bool): load settings on launch
        """
        _LOGGER.debug(' - BUILD UI')

        self.init_ui()

        _LOGGER.debug('   - RESET CALLBACKS')
        CALLBACKS_CACHE[self.mod.__name__] = self.callbacks  # pylint: disable=no-member

        for _last, _item in last(self.py_file.find_ui_elems()):
            if isinstance(_item, cpnt.PUDef):
                self.add_def(_item)
                _sep = not _last
            elif isinstance(_item, cpnt.PUSection):
                self.set_section(_item)
                _sep = False
            else:
                raise ValueError(_item)
            _LOGGER.debug('   - ADD ELEM %s sep=%d', _item, _sep)
            if _sep:
                self.add_separator()

        if load_settings:
            self.load_settings()

        self.finalize_ui()

    def init_ui(self):
        """Inititiate interface window."""
        self._build_menu_items()

    def _build_menu_items(self):
        """Build items in menu bar."""
        _file = self.add_menu('File')
        self.add_menu_item(
            _file, label='Edit',
            image=icons.EDIT,
            command=self.py_file.edit)
        self.add_menu_item(
            _file, label='Copy path',
            image=icons.COPY,
            command=wrap_fn(copy_text, self.py_file.path))

        _interface = self.add_menu('Interface')
        self.add_menu_item(
            _interface, label='Rebuild',
            image=icons.find('Hammer'),
            command=wrap_fn(self.rebuild))
        self.add_menu_separator(parent=_interface)
        self.add_menu_item(
            _interface, label='Collapse all',
            image=icons.RESET,
            command=wrap_fn(self.collapse_all))
        self.add_menu_item(
            _interface, label='Save settings',
            image=icons.SAVE,
            command=wrap_fn(self.save_settings))
        self.add_menu_item(
            _interface, label='Reset',
            image=icons.CLEAN,
            command=wrap_fn(self.reset_settings))

    def add_menu(self, name):
        """Add menu bar to the interface.

        Args:
            name (str): menu name
        """
        raise NotImplementedError

    def add_menu_separator(self, parent):
        """Add a separator item to the given menu bar.

        Args:
            parent (str): menu to add item to
        """
        raise NotImplementedError

    def add_menu_item(self, parent, label, command=None, image=None):
        """Add menu item to the given menu.

        Args:
            parent (str): menu to add item to
            label (str): item label
            command (fn): item callback
            image (str): path to item image
        """
        raise NotImplementedError

    def add_separator(self):
        """Add separator item to the interface."""
        raise NotImplementedError

    def add_def(self, def_):
        """Add function to the interface.

        Args:
            def_ (PUDef): function to add
        """
        _LOGGER.debug('ADD DEF %s', def_)
        self.init_def(def_)

        _callbacks = {'set': {}, 'get': {}, 'field': {}}
        self.callbacks['defs'][def_.name] = _callbacks
        for _arg in def_.find_args():
            _get_fn, _set_fn, _field = self.add_arg(_arg)
            _callbacks['set'][_arg.name] = _set_fn
            _callbacks['get'][_arg.name] = _get_fn
            _callbacks['field'][_arg.name] = _field

        self.finalize_def(def_)

    def init_def(self, def_):
        """Initiate new function.

        Args:
            def_ (PUDef): function to initiate
        """
        raise NotImplementedError

    def add_arg(self, arg):
        """Add argument.

        Args:
            arg (PUArg): arg to add
        """
        raise NotImplementedError

    def finalize_def(self, def_):
        """Finalize function.

        Args:
            def_ (PUDef): function to finalize
        """
        raise NotImplementedError

    @error.catch
    def _execute_def(self, def_):
        """Called when function button is pressed.

        Args:
            def_ (PUDef): function being execute
        """
        _LOGGER.debug('EXEC DEF %s', def_)

        self.save_settings()

        _callbacks = CALLBACKS_CACHE[self.mod.__name__]['defs'][def_.name]
        _kwargs = {}
        for _arg in def_.find_args():
            _LOGGER.debug('   - ARG %s', _arg)
            _callback = _callbacks['get'][_arg.name]
            _LOGGER.debug('     - CALLBACK %s', _callback)
            _kwargs[_arg.name] = _callback()
        _LOGGER.debug(' - KWARGS %s', _kwargs)

        # Execute fresh copy of def
        six_reload(self.mod)
        _LOGGER.debug(' - MOD %s', self.mod)
        def_.py_def.execute(**_kwargs)

    def set_section(self, section):
        """Set current collapsable section.

        Args:
            section (PUSection): section to apply
        """
        self._cur_section = section

    def collapse_all(self):
        """Collapse all sections."""
        raise NotImplementedError

    def finalize_ui(self):
        """Finalize building interface."""
        raise NotImplementedError

    def rebuild(self, load_settings=True):
        """Rebuild this interface.

        Args:
            load_settings (bool): load settings on rebuild
        """
        _LOGGER.debug('REBUILD')

        self.close()

        # Obtain fresh copy of class to survive reload
        _type = type(self)
        _file = abs_path(inspect.getfile(_type))
        _LOGGER.debug(' - FILE %s', _file)
        _mod = PyFile(_file).to_module()
        _LOGGER.debug(' - MOD %s', _mod)
        _class = getattr(_mod, _type.__name__)
        _LOGGER.debug(' - CLASS %s', _class)

        _launch = wrap_fn(
            _class, self.py_file.path, title=self.title, base_col=self.base_col,
            load_settings=load_settings)
        self._safe_exec_launch(_launch)

    def _safe_exec_launch(self, launch):
        """Execute launch function.

        This can be overriden if it isn't safe to launch the ui from the
        thread of an existing ui.

        Args:
            launch (fn): launch function
        """
        launch()

    def reset_settings(self, def_=None):
        """Reset interface settings.

        Args:
            def_ (PUDef): only reset settings on this function
        """
        _LOGGER.debug('RESET SETTINGS')
        if def_:
            _elem = self.py_file.find_ui_elem(def_.name)
            _LOGGER.debug(' - ELEM %s', _elem)
            _def_settings = {}
            for _arg in _elem.to_args():
                _default = _arg.py_arg.default
                _LOGGER.debug(' - ARG %s %s', _arg, _default)
                _def_settings[_arg.name] = _default
            _settings = {'defs': {_elem.name: _def_settings}}
            self.load_settings(settings=_settings)
        else:
            self.rebuild(load_settings=False)

    def load_settings(self, settings=None):
        """Load settings from disk.

        Args:
            settings (dict): override settings dict
        """
        _LOGGER.debug('LOAD SETTINGS %s', self.settings_file)
        _data = settings or self.settings_file.read_pkl(catch=True)

        # Load defs
        for _def_name, _arg_data in _data.get('defs', {}).items():
            _def_callbacks = self.callbacks['defs'].get(_def_name)
            if not _def_callbacks:
                continue
            _set_callbacks = _def_callbacks['set']
            for _arg_name, _arg_val in _arg_data.items():
                _set_fn = _set_callbacks.get(_arg_name)
                if _set_fn:
                    _set_fn(_arg_val)

        # Load sections (collapse)
        for _sect_name, _sect_val in _data.get('sections', {}).items():
            _set_fn = self.callbacks['sections'][_sect_name]['set']
            _set_fn(_sect_val)

        _LOGGER.debug(' - LOAD SETTINGS COMPLETE')

    def save_settings(self):
        """Save settings to disk."""
        _LOGGER.debug('SAVE SETTINGS %s', self.name)

        # Read args
        _data = {'defs': {}, 'sections': {}}
        _callbacks = CALLBACKS_CACHE[self.name]

        # Read defs
        for _def_name, _def_callbacks in _callbacks['defs'].items():
            _get_arg_callbacks = _def_callbacks['get']
            _def_data = {}
            for _arg_name, _arg_get in _get_arg_callbacks.items():
                _def_data[_arg_name] = _arg_get()
            if _def_data:
                _data['defs'][_def_name] = _def_data
        for _sect_name, _sect_callbacks in _callbacks['sections'].items():
            _val = _sect_callbacks['get']()
            _data['sections'][_sect_name] = _val

        self.settings_file.write_pkl(_data, force=True)
        _LOGGER.debug(' - WROTE SETTINGS %s', self.settings_file)

    def close(self):
        """Close this interface."""
        raise NotImplementedError

    def close_event(self):
        """Called when interface is closed."""
        _LOGGER.debug('CLOSE EVENT %s', self)
        self.save_settings()
