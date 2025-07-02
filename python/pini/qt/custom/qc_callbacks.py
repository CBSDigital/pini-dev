"""Tools for managing widget callbacks.

eg. for a widget called Blah, the following methods with be linked:

 -> _callback__Blah - for basic widget clicked/changed signal
 -> _redraw__Blah - for repopulating/updating widget
 -> _context__Blah - for right-clicking widget

If any of these functions exists and the Blah widget is not found, an
error will be thrown.
"""

import logging

from pini.utils import wrap_fn

from ..q_mgr import QtWidgets, Qt

_LOGGER = logging.getLogger(__name__)


def connect_callbacks(
        dialog, ui=None, settings_container=None, error_catcher=None,
        disconnect=False):
    """Connect all callbacks for the given dialog.

    Args:
        dialog (CUIDialog): dialog to connect
        ui (CUiContainer): override ui container (if not dialog.ui)
        settings_container (any): parent object for settings
        error_catcher (fn): error catcher decorator
        disconnect (bool): disconnect signal before connecting callback
    """
    _LOGGER.debug('CONNECT CALLBACKS %s', dialog)
    _ui = ui or dialog.ui
    _settings_container = settings_container or dialog
    _connect_simple_callbacks(
        dialog, ui=_ui, disconnect=disconnect,
        error_catcher=error_catcher)
    _connect_save_on_change(
        ui=_ui, settings_container=_settings_container)
    _connect_redraws(dialog, ui=_ui, error_catcher=error_catcher)
    _connect_pixmap_draws(dialog, ui=_ui)
    _connect_contexts(
        dialog, ui=_ui, error_catcher=error_catcher, disconnect=disconnect)
    _LOGGER.debug(' - CONNECT CALLBACKS COMPLETE %s', dialog)


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
        _LOGGER.debug('CONTEXT FN %s %s %s', name, callback, dialog)
        from pini import qt
        _widget = dialog.ui.find_widget(name)
        _LOGGER.debug(' - FOUND WIDGET %s', _widget)
        _menu = qt.CMenu(_widget)
        callback(_menu)
        _LOGGER.debug(' - BUILT MENU %s', _menu)
        _menu.exec_(_widget.mapToGlobal(pos))
        _LOGGER.debug(' - COMPLETE %s', name)

    return _context_fn


def _connect_contexts(dialog, ui, error_catcher, disconnect):
    """Connect context callbacks based on method name.

    This builds a menu when the element is right-clicked, and then
    passes that menu to the corresponding context method to be
    populated.

    eg. _context__PushButton is connected to ui.PushButton.

    Args:
        dialog (CUIDialog): dialog to connect
        ui (CUiContainer): override ui container (if not dialog.ui)
        error_catcher (fn): error catcher decorator
        disconnect (bool): replace existing connections on connect
    """
    _LOGGER.debug(' - CONNECTING CONTEXTS %s', dialog)
    _contexts = [getattr(dialog, _name)
                 for _name in dir(dialog)
                 if _name.startswith('_context__')]

    for _context in _contexts:

        if error_catcher:
            _context = error_catcher(_context)

        # Obtain widget
        _LOGGER.debug('   - CONNECTING CONTEXT %s', _context)
        _widget_name = _context.__name__[len('_context__'):]
        _widget = getattr(ui, _widget_name, None)
        if not _widget:
            raise RuntimeError(
                f'Missing context widget {_widget_name}: {_context}')
        if not hasattr(_widget, 'customContextMenuRequested'):
            raise RuntimeError(f'Bad widget type {_widget_name}')

        # Connnect context callback
        if disconnect:
            _widget.customContextMenuRequested.disconnect()
        _widget.customContextMenuRequested.connect(
            _build_context_fn(
                callback=_context, dialog=dialog, name=_widget.objectName()))
        _widget.setContextMenuPolicy(Qt.CustomContextMenu)


def _connect_pixmap_draws(dialog, ui):
    """Connect pixmap draw functions for CPixmapLabel widgets.

    eg. _draw__Blah is applied to ui.Blah.draw_pixmap_func

    Args:
        dialog (CUIDialog): dialog to connect
        ui (CUiContainer): override ui container (if not dialog.ui)
    """
    from pini import qt

    _LOGGER.debug('   - CONNECT PIXMAP DRAWS %s', dialog)
    _draw_fns = [
        getattr(dialog, _name) for _name in dir(dialog)
        if _name.startswith('_draw__')]

    for _draw_fn in _draw_fns:
        _, _widget_name = _draw_fn.__name__.split('__')
        _widget = getattr(ui, _widget_name, None)
        if not _widget:
            raise RuntimeError(
                f'Draw method {_draw_fn.__name__} is missing '
                f'widget ({_widget_name})')
        _LOGGER.debug('     - CONNECT %s -> %s', _draw_fn, _widget)
        assert isinstance(_widget, qt.CPixmapLabel)
        _widget.draw_pixmap_func = _draw_fn


def _connect_redraws(dialog, ui, error_catcher):
    """Connect redraw callbacks based on method name.

    eg. _redraw__PushButton is connected to ui.PushButton.

    Args:
        dialog (CUIDialog): dialog to connect
        ui (CUiContainer): override ui container (if not dialog.ui)
        error_catcher (fn): error catcher decorator
    """
    _LOGGER.debug('   - CONNECT REDRAWS %s', dialog)
    _redraws = [
        getattr(dialog, _name) for _name in dir(dialog)
        if _name.startswith('_redraw__')]

    for _redraw in _redraws:

        if error_catcher:
            _redraw = error_catcher(_redraw)

        # Obtain widget
        _LOGGER.debug('     - CONNECTING REDRAW %s', _redraw)
        _widget_name = _redraw.__name__[len('_redraw__'):]
        _widget = getattr(ui, _widget_name, None)
        if not _widget:
            raise RuntimeError(
                f'Redraw method {_redraw.__name__} is missing '
                f'widget ({_widget_name})')

        # Connnect redraw callback
        _widget.redraw = _redraw


def _connect_save_on_change(ui, settings_container):
    """Connect save on change callback.

    Args:
        ui (CUiContainer): override ui container (if not dialog.ui)
        settings_container (any): parent object for settings
    """
    from pini import qt
    _LOGGER.debug(' - CONNECT SAVE ON CHANGE')
    _widgets = [
        _item for _item in ui.__dict__.values()
        if isinstance(_item, qt.CBaseWidget)]
    for _widget in _widgets:
        _signal = qt.widget_to_signal(_widget)
        if not _signal:
            continue
        _LOGGER.debug('   - CONNECTING SAVE ON CHANGE %s', _widget)
        _signal.connect(
            wrap_fn(
                _widget.apply_save_policy_on_change,
                settings_container.settings))


def _connect_signal_callback(
        dialog, ui, callback, error_catcher, disconnect=False):
    """Connect a callback to its widget.

    Args:
        dialog (CUIDialog): dialog to connect
        ui (CUiContainer): override ui container (if not dialog.ui)
        callback (fn): callback to connect
        error_catcher (fn): error catcher decorator
        disconnect (bool): replace existing connections on connect
    """
    from pini import qt

    # Obtain widget
    _callback = callback
    _widget_name = _callback.__name__[len('_callback__'):]
    _widget = getattr(ui, _widget_name, None)
    if not _widget:
        raise RuntimeError(
            f'Missing callback widget {_widget_name}: {_callback}')

    # Find signal to connect
    _signal = qt.widget_to_signal(_widget)

    # Prepare callback
    _callback = wrap_fn(_callback)  # Ignore any args/kwargs
    if isinstance(_widget, QtWidgets.QPushButton):
        if error_catcher:
            _callback = error_catcher(_callback)
        _callback = _disable_on_execute(
            func=_callback, dialog=dialog, name=_widget_name)
    elif isinstance(_widget, qt.CLabel):
        _widget.callback = _callback

    _LOGGER.debug(
        '   - CONNECT SIMPLE CALLBACK %s %s %s',
        _widget.objectName() if hasattr(_widget, 'objectName') else '-',
        _widget, _callback)

    # Make connections
    if _signal:
        if disconnect:
            _LOGGER.debug('    - DISCONNECT CALLBACK %s %s', _widget, _signal)
            try:
                _signal.disconnect()
            except RuntimeError:
                _LOGGER.info(
                    '    - DISCONNECT CALLBACK FAILED %s %s', _widget, _signal)
        _signal.connect(_callback)


def _connect_simple_callbacks(
        dialog, ui, error_catcher, disconnect=False):
    """Connect callbacks based on method name.

    Any method with name matching a ui element will be connected,
    and if a callback method is found without a matching ui element
    then an error is thrown.

    eg. _callback__PushButton is connected to ui.PushButton

    Args:
        dialog (CUIDialog): dialog to connect
        ui (CUiContainer): override ui container (if not dialog.ui)
        error_catcher (fn): error catcher decorator
        disconnect (bool): replace existing connections on connect
    """
    _LOGGER.debug(' - CONNECT SIMPLE CALLBACKS')
    _callbacks = [
        getattr(dialog, _name) for _name in dir(dialog)
        if _name.startswith('_callback__')]
    _LOGGER.debug(
        '   - FOUND %d SIMPLE CALLBACKS IN %s', len(_callbacks), dialog)

    for _callback in _callbacks:
        _connect_signal_callback(
            dialog, callback=_callback, ui=ui, disconnect=disconnect,
            error_catcher=error_catcher)


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
