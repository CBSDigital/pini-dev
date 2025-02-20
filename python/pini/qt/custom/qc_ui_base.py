"""Tools for managing the base class for a managed ui interface."""

# pylint: disable=too-many-instance-attributes

import logging
import os
import re
import sys

from pini import dcc, icons
from pini.utils import (
    TMP_PATH, abs_path, File, cache_property, nice_id, to_pascal, wrap_fn,
    passes_filter, single, strftime, check_logging_level)

from ..q_ui_container import CUiContainer
from ..q_utils import (
    SETTINGS_DIR, find_widget_children, p_is_onscreen, nice_screen,
    screen_is_available)
from ..q_layout import find_layout_widgets
from ..q_mgr import QtWidgets, QtGui, Qt, QtCore

_LOGGER = logging.getLogger(__name__)


class CUiBase:
    """Base class for any managed ui interface."""

    timer = None

    def __init__(
            self, ui_file, stack_key=None, load_settings=True, show=True,
            catch_errors=True, modal=False, ui_loader=None, title=None,
            settings_file=None, settings_suffix=None, fps=None):
        """Constructor.

        Args:
            ui_file (str): path to ui file
            stack_key (str): stack key (default is ui path)
                closes any previous instance of the dialog
                before launching a new one
            load_settings (bool): load settings on launch
            show (bool): show interface on launch
            catch_errors (bool): decorate callbacks with error catcher
            modal (bool): execute dialog modally
            ui_loader (QUiLoader): override ui loader
            title (str): override window title
            settings_file (File): override path to settings file
            settings_suffix (str): apply suffix to default settings
                file name
            fps (float): start timer at the given frame rate
        """

        # Setup basic vars
        self._successful_load = False
        self.ui_file = abs_path(ui_file)
        self.name = type(self).__name__

        self.shortcuts = {
            'q': (self.close, 'Quit'),
            Qt.Key_Escape: (self.close, 'Quit'),
        }

        # Init settings
        self._settings_name = File(ui_file).base
        if settings_suffix:
            self._settings_name += settings_suffix
        self._settings_file = settings_file
        self.store_settings = load_settings

        # Setup dialog stack
        self._dialog_stack_key = stack_key or self.ui_file
        self._register_in_dialog_stack()

        # Set up error catcher
        self._error_catcher = None
        if catch_errors:
            from pini.tools import error
            self._error_catcher = error.get_catcher(qt_safe=True)

        # Setup ui
        self._ui = self.ui = None
        self._load_ui(ui_file=ui_file, ui_loader=ui_loader)
        self.init_ui()

        # Initiate interface
        if self.store_settings:
            self.load_settings(type_filter='-QSplitter')
        if not modal and show:
            self.show()
        if self.store_settings:
            self.load_settings(type_filter='QSplitter')
        if title:
            self.setWindowTitle(title)

        self._apply_default_font_size()
        self._check_tooltips()
        self._connect_redraws()
        self._connect_callbacks()
        self._connect_contexts()

        # Setup QHBoxLayout size policies cache to fix bad transfer
        # from designer to nuke
        _file = File(self.ui_file)
        self._hbox_size_policies_yml = _file.to_file(
            base=_file.base + '_hsp', extn='yml', hidden=True)
        if dcc.NAME == 'nuke':
            self.fix_hbox_size_policies()

        if fps:
            self.start_timer(fps=fps)

        self._successful_load = True

        if modal:
            self.exec_()

    def init_ui(self):
        """To be implemented in subclass."""

    def _register_in_dialog_stack(self):
        """Register this dialog in the dialog stack.

        Any existing dialog with this ui file is closed.
        """
        # pylint: disable=no-member
        if self._dialog_stack_key in sys.QT_DIALOG_STACK:
            sys.QT_DIALOG_STACK[self._dialog_stack_key].delete()
        sys.QT_DIALOG_STACK[self._dialog_stack_key] = self

    def _load_ui(
            self, ui_file, ui_loader=None, fix_icon_paths=True):
        """Load ui file into ui object.

        Args:
            ui_file (str): path to ui file
            ui_loader (QUiLoader): override ui loader
            fix_icon_paths (bool): update icon paths
                to be relative to current pini_icons module
        """
        from pini import qt

        # Load ui
        _ui_file = ui_file
        _LOGGER.debug('LOADING UI FILE %s', _ui_file)
        if fix_icon_paths:
            _ui_file = _fix_icon_paths(_ui_file)
            _LOGGER.debug(' - UPDATED UI FILE %s', _ui_file)
        _loader = ui_loader or qt.build_ui_loader()
        self._ui = _loader.load(_ui_file)

        # Link to this instance based on type
        if isinstance(self._ui, QtWidgets.QMainWindow):
            assert isinstance(self, QtWidgets.QMainWindow)
            self.setCentralWidget(self._ui.centralWidget())
        elif isinstance(self._ui, QtWidgets.QWidget):
            assert isinstance(self, QtWidgets.QWidget)
            self._ui.setParent(self)
        else:
            raise ValueError(self._ui)
        self.adjustSize()

        # Connect/store layout
        self._ui_layout = self._ui.layout()
        _LOGGER.debug(' - LAYOUT %s', self._ui_layout)
        if self._ui_layout:
            if not self._ui_layout.objectName():
                _name = to_pascal(File(ui_file).base)
                self._ui_layout.setObjectName(_name)
            self.setLayout(self._ui_layout)

        self.setWindowTitle(self._ui.windowTitle())

        self.ui = _UiHandler(dialog=self, ui=self._ui)

        return self._ui

    def add_shortcut(self, key, action, label):
        """Add shortcut for this interface.

        Args:
            key (str): shortcut key
            action (fn): shortcut action
            label (str): shortcut label
        """
        self.shortcuts[key] = action, label

    def start_timer(self, fps):
        """Start timer at the given frame rate.

        Args:
            fps (float): frame rate of timer event
        """
        _ms = int(1000 / fps)
        _LOGGER.info('START TIMER fps=%.01f ms=%d', fps, _ms)
        self.timer = self.startTimer(_ms)

    def rebuild_ui(self):
        """Rebuild ui object using a dummy namespace.

        This is used to fix over-aggressive garbage collection in PySide in
        maya, which will often delete the elements attached to the ui.

        Returns:
            (DummyUi): rebuilt ui
        """
        _LOGGER.debug('REBUILD UI %s', self)

        self._ui = CUiContainer()
        for _widget in find_widget_children(self):
            if isinstance(_widget, (QtWidgets.QSpacerItem,
                                    QtWidgets.QWidgetItem,
                                    QtWidgets.QListWidgetItem)):
                continue
            _name = _widget.objectName()
            if not _name:
                continue
            setattr(self._ui, _name, _widget)
        self._connect_callbacks(disconnect=True)

        _LOGGER.debug(' - REBUILD UI COMPLETE')

        return self._ui

    def find_widgets(self, filter_=None, class_=None):
        """Find widgets belonging to this interface.

        Args:
            filter_ (str): filter results by name
            class_ (class): filter by widget class

        Returns:
            (QWidget list): widgets
        """
        assert isinstance(self.ui, _UiHandler)
        return self.ui.find_widgets(filter_=filter_, class_=class_)

    def _apply_default_font_size(self):
        """Setup default font size via $PINI_DEFAULT_FONT_SIZE."""
        _size = os.environ.get('PINI_DEFAULT_FONT_SIZE')
        if _size:
            _size = int(_size)
            self.setStyleSheet(f'font-size: {_size:d}pt')

    def _check_tooltips(self):
        """Check tooltips.

        This makes sure all image buttons have tooltips and that there
        are no duplicate tooltips (this might arise from copying and
        pasting elements in designer).
        """
        _LOGGER.debug('CHECK TOOLTIPS')
        _tooltips = {}
        for _widget in self.find_widgets():

            if isinstance(_widget, QtWidgets.QLayout):
                continue

            _tooltip = _widget.toolTip()
            _LOGGER.debug(' - CHECKING %s %s', _widget.objectName(), _tooltip)

            # Check for duplicate tooltips
            if _tooltip:
                if _tooltip in _tooltips:
                    _widget_a = _tooltips[_tooltip]
                    _widget_b = _widget.objectName()
                    raise RuntimeError(
                        f'Duplicate tooltips in {_widget_a} and {_widget_b}')
                _tooltips[_tooltip] = _widget.objectName()

            # Check image buttons have tooltip
            if isinstance(_widget, QtWidgets.QPushButton):
                _LOGGER.debug(' - TEXT %s', _widget.text())
                if not _widget.text() and not _tooltip:
                    _widget = _widget.objectName()
                    raise RuntimeError(
                        f'No tooltip for image button {_widget}')

    def _connect_callback(self, callback, disconnect=False):
        """Connect a callback to its widget.

        Args:
            callback (fn): callback to connect
            disconnect (bool): replace existing connections on connect
        """
        from pini import qt

        # Obtain widget
        _callback = callback
        _widget_name = _callback.__name__[len('_callback__'):]
        _widget = getattr(self._ui, _widget_name, None)
        if not _widget:
            raise RuntimeError(f'Missing callback widget {_widget_name}')

        # Find signal to connect
        _signal = qt.widget_to_signal(_widget)
        if isinstance(_widget, QtWidgets.QPushButton):
            if self._error_catcher:
                _callback = self._error_catcher(_callback)
            _callback = _disable_on_execute(
                func=_callback, dialog=self, name=_widget_name)
        elif isinstance(_widget, qt.CLabel):
            _widget.callback = _callback

        _LOGGER.debug(
            ' - CONNECT CALLBACK %s %s %s',
            _widget.objectName() if hasattr(_widget, 'objectName') else '-',
            _widget, _callback)

        # Make connections
        if _signal:
            if disconnect:
                _LOGGER.debug(' - DISCONNECT CALLBACK %s %s', _widget, _signal)
                try:
                    _signal.disconnect()
                except RuntimeError:
                    _LOGGER.info(
                        ' - DISCONNECT CALLBACK FAILED %s %s', _widget, _signal)
            _signal.connect(_callback)

            # Apply save on change save policy
            if isinstance(_widget, qt.CBaseWidget):
                _signal.connect(
                    wrap_fn(_widget.apply_save_policy_on_change, self.settings))

    def _connect_callbacks(self, disconnect=False):
        """Connect callbacks based on method name.

        Any method with name matching a ui element will be connected,
        and if a callback method is found without a matching ui element
        then an error is thrown.

        eg. _callback__PushButton is connected to ui.PushButton

        Args:
            disconnect (bool): replace existing connections on connect
        """
        _LOGGER.debug('CONNECT CALLBACKS')
        _callbacks = [getattr(self, _name)
                      for _name in dir(self)
                      if _name.startswith('_callback__')]

        for _callback in _callbacks:
            self._connect_callback(_callback, disconnect=disconnect)

    def _connect_contexts(self):
        """Connect context callbacks based on method name.

        This builds a menu when the element is right-clicked, and then
        passes that menu to the corresponding context method to be
        populated.

        eg. _context__PushButton is connected to ui.PushButton.
        """
        _contexts = [getattr(self, _name)
                     for _name in dir(self)
                     if _name.startswith('_context__')]

        for _context in _contexts:

            if self._error_catcher:
                _context = self._error_catcher(_context)

            # Obtain widget
            _LOGGER.debug('CONNECTING CONTEXT %s', _context)
            _widget_name = _context.__name__[len('_context__'):]
            _widget = getattr(self.ui, _widget_name, None)
            if not _widget:
                raise RuntimeError('Missing context widget ' + _widget_name)

            # Connnect context callback
            _widget.customContextMenuRequested.connect(
                _build_context_fn(
                    _context, dialog=self, name=_widget.objectName()))
            _widget.setContextMenuPolicy(Qt.CustomContextMenu)

    def _connect_redraws(self):
        """Connect redraw callbacks based on method name.

        eg. _redraw__PushButton is connected to ui.PushButton.
        """
        _redraws = [getattr(self, _name)
                    for _name in dir(self)
                    if _name.startswith('_redraw__')]

        for _redraw in _redraws:

            if self._error_catcher:
                _redraw = self._error_catcher(_redraw)

            # Obtain widget
            _LOGGER.debug('CONNECTING REDRAW %s', _redraw)
            _widget_name = _redraw.__name__[len('_redraw__'):]
            _widget = getattr(self.ui, _widget_name, None)
            if not _widget:
                raise RuntimeError(
                    f'Redraw method {_redraw.__name__} is missing '
                    f'widget ({_widget_name})')

            # Connnect redraw callback
            _widget.redraw = _redraw

    def set_window_icon(self, icon):
        """Set window icon.

        Args:
            icon (str): path to icon
        """
        _icon = QtGui.QIcon(icon)
        self.setWindowIcon(_icon)

    def save_hbox_size_policies(self):
        """Save hbox layout size policies.

        This read the horizonal size policies of all widgets in
        QHBoxLayout layouts and saves them to a hidden hsp.yml
        in the same directory as the ui file.

        This allows them to be applied in nuke, whose ui loader
        seems to lose this information.
        """
        assert dcc.NAME == 'maya'
        _LOGGER.debug('SAVE HBOX SIZE POLICIES %s', self)
        _hsps = {}
        for _lyt in self.find_widgets(class_=QtWidgets.QHBoxLayout):
            _LOGGER.debug(' - LAYOUT %s', _lyt.objectName())
            for _widget in find_layout_widgets(_lyt):
                _hsp = _widget.sizePolicy().horizontalPolicy().name
                _hsp = str(_hsp.decode('utf8'))  # py3 uses bytes
                if isinstance(_widget, QtWidgets.QSpacerItem):
                    continue
                _name = str(_widget.objectName())
                _hsps[_name] = _hsp
                _LOGGER.debug('   - WIDGET %s %s', _widget.objectName(), _hsp)
        self._hbox_size_policies_yml.write_yml(_hsps, force=True)

    def fix_hbox_size_policies(self):
        """Fix hbox layout size policies.

        If the horizonal file policies of QHBoxLayout widgets has been
        saved to the hsp.yml file, this restores their values from the
        saved file.

        This is to fix a bug in nuke where this information is lost
        by the ui loader.
        """
        _LOGGER.debug(
            'FIX HBOX SIZE POLICIES %s', self._hbox_size_policies_yml.path)
        assert dcc.NAME == 'nuke'
        if not self._hbox_size_policies_yml.exists():
            _LOGGER.debug(
                ' - MISSING YML %s', self._hbox_size_policies_yml.path)
            return
        _hsps = self._hbox_size_policies_yml.read_yml()
        for _name, _hsp in _hsps.items():
            _LOGGER.debug(' - APPLYING %s %s', _name, _hsp)
            _widget = self.ui.find_widget(_name, catch=True)
            if not _widget:
                _LOGGER.debug(' - WIDGET NOT FOUND')
                continue
            _hsp = getattr(QtWidgets.QSizePolicy, _hsp)
            _cur_sp = _widget.sizePolicy()
            _widget.setSizePolicy(_hsp, _cur_sp.verticalPolicy())

    @cache_property
    def settings(self):
        """Obtain the settings object.

        Returns:
            (QSettings): settings
        """
        from pini import qt
        _dcc = '_' + dcc.NAME if dcc.NAME else ''
        _settings_file = self._settings_file or abs_path(
            f'{SETTINGS_DIR}/{self._settings_name}{_dcc}.ini')
        File(_settings_file).touch()  # Check settings writable
        return qt.CSettings(_settings_file)

    def load_setting(self, widget):
        """Load a widget setting.

        Args:
            widget (QWidget): widget to update
        """
        self.settings.apply_to_widget(widget)

    def load_settings(self, geometry=True, type_filter=None):
        """Load interface settings.

        Args:
            geometry (bool): load window position/size
            type_filter (str): apply widget type name filter
        """
        _LOGGER.debug('LOAD SETTINGS %s', self.settings.fileName())

        # Apply window settings
        if geometry:
            self._load_geometry_settings()

        self.settings.apply_to_ui(self.ui, type_filter=type_filter)

    def _load_geometry_settings(self, screen=None):
        """Load geometry settings (ie. pos/size).

        Load geometry is blocked if the saved position is outside any of
        the current screen regions. This can occur if screens are added or
        removed, and can cause dccs to become locked if modal interfaces
        are not visible.

        Args:
            screen (str): override screen

        Returns:
            (bool): whether geometry settings were loaded successfully
        """
        _LOGGER.debug(' - LOAD GEOMETRY SETTINGS')

        # Read pos/size
        _pos = self.settings.value('window/pos')
        _size = self.settings.value('window/size')
        if not _pos or not _size:
            _LOGGER.debug('   - POS/SIZE SETTINGS NOT FOUND')
            return False

        _screen = screen or self.settings.value('window/screen')
        _LOGGER.debug('   - GEO pos=%s size=%s screen=%s', _pos, _size, _screen)
        if not p_is_onscreen(_pos) and not screen_is_available(_screen):
            _LOGGER.debug('   - REJECTING LOAD GEOMETRY, POS IS OFFSCREEN')
            return False

        _LOGGER.debug('   - APPLYING GEOMETRY')
        self.move(_pos)
        self.resize(_size)
        return True

    def save_settings(self, filter_=None, pos=None):
        """Save settings to disk.

        Args:
            filter_ (str): filter settings by widget name
            pos (bool): save window postion - by default this will only happen
                if the window is visible; there is a bug in PySide where if
                you close a window is seems to move 21 pixel south which
                causes the position to shift each time, so this is to prevent
                that from happening
        """
        _LOGGER.debug('SAVE SETTINGS %s', self.settings.fileName())

        # Save pos
        _pos = pos if pos is not None else self.isVisible()
        if _pos:
            self.settings.setValue('window/pos', self.pos())
            _LOGGER.debug(' - SAVING POS %s', self.pos())

        # Save size
        self.settings.setValue('window/size', self.size())
        _LOGGER.debug(' - SAVING SIZE %s', self.size())

        # Save screen
        _screen = nice_screen(self.screen())
        _LOGGER.debug(' - SAVING SCREEN %s', _screen)
        self.settings.setValue('window/screen', _screen)

        self.settings.save_ui(self.ui, filter_=filter_)

    def delete(self):
        """Delete this interface."""
        _name = self.name
        _LOGGER.debug('DELETE CUiBase %s', _name)

        # Obtain list of actions to try
        _actions = [('close', self.close)]
        if self.timer:
            _actions += [('kill timer', wrap_fn(self.killTimer, self.timer))]
        if self._successful_load and self.store_settings:
            _actions += [('save settings', self.save_settings)]
        _actions += [('delete', self.deleteLater)]

        # Attempt to execute each action
        for _label, _action in _actions:
            try:
                _action()
            except RuntimeError as _exc:
                _LOGGER.info(' - ACTION %s ERRORED - %s', _label, _name)

        _LOGGER.debug(' - DELETE %s COMPLETE', self.name)

    def closeEvent(self, event=None):
        """Triggered by close.

        Args:
            event (QEvent): close event
        """
        del event  # For linter
        _LOGGER.debug('CLOSE EVENT')
        self.save_settings(pos=True)
        if self.timer:
            self.killTimer(self.timer)

    def deleteLater(self):
        """Remove this interface.

        Make sure close event is run.
        """
        _LOGGER.debug('DELETE LATER')
        self.closeEvent(event=None)

    def keyPressEvent(self, event):
        """Executed on key press.

        Args:
            event (QEvent): key press event
        """
        _LOGGER.debug(
            'KEY PRESS EVENT text=%s key=%s', event.text(), event.key())
        for _key, (_action, _label) in self.shortcuts.items():
            if event.text() == _key or event.key() == _key:
                _LOGGER.info(' - APPLYING SHORTCUT %s %s', _label, _action)
                _action()  # pylint: disable=not-callable

    def timerEvent(self, event):
        """Triggered by timer.

        Kills the timer if the ui isn't visible.

        Args:
            event (QTimerEvent): triggered event
        """
        check_logging_level()
        _LOGGER.debug(
            'TIMER EVENT [%s] %s', nice_id(self), strftime('%H:%M:%S'))
        if (
                self.timer and
                self._successful_load and
                not self.isVisible()):
            self.killTimer(self.timer)
            _LOGGER.info(
                'KILLED TIMER event=%s timer=%s visible=%d',
                event, self.timer, self.isVisible())

    def __repr__(self):
        _name = type(self).__name__.strip('_')
        return f'<{_name}>'


class CUiBaseDummy(CUiBase):
    """Dummy class to fix PySide6/py11 inheritance.

    In this configuration qt seems to call __init__ on all parent classes
    when __init__ is called on the QObject class - this dummy allows the
    parent __init__ to be disabled so that it can be called manually.
    """

    def __init__(self, **kwargs):  # pylint: disable=super-init-not-called
        """Constructor."""


def _rebuild_ui_on_error(func):
    """Decorator to catch garbage collector issues.

    This decorator can be applied to method methods on the ui
    handler. If the ui errors with an error due to over-aggressive
    garbage collection (which seems to occur in maya), the ui is
    rebuilt, and the function is executed again.

    Args:
        func (fn): method to decorate

    Returns:
        (fn): decorated method
    """

    def _rebuild_ui_func(self, *args, **kwargs):
        assert isinstance(self, _UiHandler)
        try:
            _result = func(self, *args, **kwargs)
        except RuntimeError as _exc:
            _LOGGER.info('UI WAS GARGAGE COLLECTED - REBUILDING %s',
                         self.dialog)
            if (
                    not str(_exc).startswith('Internal C++ object') or
                    not str(_exc).endswith('already deleted.')):
                _LOGGER.info(' - UNHANDLED ERROR "%s"', _exc)
                raise _exc
            self.rebuild_ui()
            _result = func(self, *args, **kwargs)
        return _result

    return _rebuild_ui_func


class _UiHandler:
    """Handler for ui object.

    Sometimes the garbage collector in PySide in maya will delete elements
    attached to the ui object, and requesting them will raise an error saying
    that the internal C++ object has already been deleted.

    If this happens, the ui object will be reconstructed automatically in
    a dummy namespace.
    """

    def __init__(self, dialog, ui):
        """Constructor.

        Args:
            dialog (QDialog): parent dialog
            ui (QWidget): ui object
        """
        self.ui = ui
        self.dialog = dialog

    @_rebuild_ui_on_error
    def find_widget(self, name, catch=True, case_sensitive=False):
        """Find a widget within this ui container.

        Args:
            name (str): name to match
            catch (bool): no error if widget not found
            case_sensitive (bool): ignore case (this is enabled by default
                as windows saves QSettings keys with unreliable case)

        Returns:
            (QWidget): matching widget
        """
        try:
            if case_sensitive:
                return single([_widget for _widget in self.find_widgets()
                               if _widget.objectName() == name], catch=catch)
            return single([
                _widget for _widget in self.find_widgets()
                if _widget.objectName().lower() == name.lower()], catch=catch)
        except ValueError as _exc:
            raise ValueError('Failed to find widget ' + name) from _exc

    @_rebuild_ui_on_error
    def find_widgets(self, filter_=None, class_=None):
        """Find widgets belonging to this interface.

        Args:
            filter_ (str): filter by widget name
            class_ (class): filter by widget type

        Returns:
            (QWidget list): widgets
        """
        _LOGGER.log(9, 'FIND WIDGETS %s type=%s', self, class_)
        _widgets = []
        for _name in dir(self.ui):

            if filter_ and not passes_filter(_name, filter_):
                continue

            _widget = getattr(self.ui, _name)
            if not isinstance(_widget, QtCore.QObject):
                continue
            if class_ and not isinstance(_widget, class_):
                continue

            # Check object hasn't been garbage collected
            _widget.objectName()

            _widgets.append(_widget)
        return _widgets

    def rebuild_ui(self):
        """Rebuild ui container.

        This may be necessary due to over-aggressive garbage collection
        applied to PySide in maya.
        """
        self.ui = self.dialog.rebuild_ui()

    def __getattr__(self, attr):

        _result = getattr(self.ui, attr)

        if isinstance(_result, QtWidgets.QSpacerItem):
            _LOGGER.warning('UI getattr %s RETURNED SPACER - REBUILDING', attr)
        else:
            try:
                _name = _result.objectName()
            except RuntimeError as _exc:
                assert str(_exc).startswith('Internal C++ object')
                assert str(_exc).endswith('already deleted.')
            else:
                return _result
            _LOGGER.info('UI GARGAGE COLLECTED (%s) - REBUILDING', attr)

        # Rebuild ui object
        self.rebuild_ui()
        return getattr(self.ui, attr)


def _build_context_fn(callback, dialog, name):
    """Build a context function for the given widget.

    This function is called on right click. It builds a QMenu which can
    then be populated by the context method in the dialog class.

    Due to garbage collection issues, the parent dialog and the element
    name are used rather than just the widget (ie. so the widget can be
    retrieved if it gets garbage collected).

    Args:
        callback (fn): context method in dialog class
        dialog (QDialog): parent dialog
        name (str): widget name

    Returns:
        (fn): context function
    """

    def _context_fn(pos):
        from pini import qt
        _widget = dialog.ui.find_widget(name)
        _menu = qt.CMenu(_widget)
        callback(_menu)
        _menu.exec_(_widget.mapToGlobal(pos))

    return _context_fn


def _disable_on_execute(func, dialog, name):
    """Decorates a widget callback so that it is disabled during execution.

    The ui handler and widget name are required in case garbage collection
    issues occur, and the widget needs to be rediscovered.

    Args:
        func (fn): function to decorate
        dialog (QDialog): parent dialog
        name (str): widget name

    Returns:
        (fn): decorated function
    """

    def _func(*args, **kwargs):

        _widget = dialog.ui.find_widget(name)
        _widget.setEnabled(False)

        try:
            _result = func(*args, **kwargs)
        finally:
            _widget.setEnabled(True)
            if hasattr(_widget, 'redraw'):
                _widget.redraw()

        return _result

    return _func


def _fix_icon_paths(ui_file, force=False):
    """Fix icon paths.

    This builds a tmp version of the ui file with paths updated to
    point at the current location of pini-icons repository.

    Args:
        ui_file (str): path to ui file
        force (bool): force generate tmp ui file, even if it's
            newer that the latest ui file

    Returns:
        (str): path to tmp ui file
    """
    from pini import pipe
    _LOGGER.debug('FIX ICON PATHS %s', ui_file)

    _ui_file = File(ui_file)
    _path_cpnt = abs_path(ui_file).replace(':', '')
    _fixed_ui = File(f'{TMP_PATH}/pini/{_path_cpnt}')

    # Check if fixed file is outdated
    _fixed_exists = _fixed_ui.exists()
    if _fixed_exists:
        _ui_mtime = _ui_file.mtime()
        _fixed_mtime = _fixed_ui.mtime()
        _fixed_outdated = _fixed_mtime < _ui_mtime
    else:
        _fixed_outdated = None
    _LOGGER.debug('FIX ICONS PATHS fixed_exists=%s fixed_outdated=%s',
                  _fixed_exists, _fixed_outdated)

    if force or not _fixed_exists or _fixed_outdated:

        _LOGGER.debug('FIXED UI %s', _fixed_ui)
        _body = _ui_file.read()
        _fixed = set()
        for _chunk in re.split('[<>]', _body):
            if (
                    not _chunk.startswith('..') or
                    _chunk in _fixed):
                continue
            _path = abs_path(_chunk, root=_ui_file.dir)
            _path = pipe.map_path(_path)
            if '/pini-icons/' in _path:
                _, _tail = _path.split('/pini-icons/')
                _path = f'{icons.ICONS_ROOT}/{_tail}'
            _LOGGER.debug(' - PATH %s', _path)
            if not os.path.exists(_path):
                raise RuntimeError('Missing path ' + _path)
            assert File(_path).exists()
            _body = _body.replace(_chunk, _path)
            _fixed.add(_chunk)

        _LOGGER.debug('COMPILED TMP UI FILE %s', _fixed_ui.path)
        _fixed_ui.write(_body, force=True)

    return _fixed_ui.path
