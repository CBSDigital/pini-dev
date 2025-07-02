"""General qt utilities."""

import enum
import functools
import logging
import os
import sys

from pini.utils import (
    cache_result, single, passes_filter, check_heart,
    basic_repr, File, build_cache_fmt, check_logging_level, HOME)

from .q_mgr import QtWidgets, QtCore, QtGui, LIB

_LOGGER = logging.getLogger(__name__)
SETTINGS_DIR = HOME.to_subdir('.pini/settings').path

X_AXIS = QtCore.QPoint(1, 0)
Y_AXIS = QtCore.QPoint(0, 1)


class DialogCancelled(RuntimeError):
    """Raise on dialog cancelled."""


class SavePolicy(enum.IntEnum):
    """Enum to manage widget save policy options.

    NOTE: Start numbering at zero so that boolean of DEFAULT is still
    non-zero.
    """

    DEFAULT = 1
    NO_SAVE = 2
    SAVE_ON_CHANGE = 3
    SAVE_IN_SCENE = 4
    SAVE_ON_CLOSE = 5


def block_signals(func):
    """Block widget signals on execute.

    Args:
        func (fn): method to decorate

    Returns:
        (fn): decorated method
    """

    def _block_func(widget, *args, **kwargs):
        _blocked = widget.signalsBlocked()
        _LOGGER.debug('BLOCK SIGNALS %s %s', widget, _blocked)
        widget.blockSignals(True)
        _result = func(widget, *args, **kwargs)
        widget.blockSignals(_blocked)
        _LOGGER.debug(' - BLOCK SIGNALS COMPLETE %s %s', widget, _blocked)
        return _result

    return _block_func


def build_tmp_icon(
        file_, base, overlay, base_scale=None, over_scale=0.45,
        mode='Map File'):
    """Build tmp icon.

    This allows an icon to be built on the fly (eg. for maya shelf) by
    overlaying an existing icon over another one. The path is automatically
    assigned using a file path as the uid.

    Args:
        file_ (str): file to use as uid for tmp path - generally this is
            the path to the module which the icon belongs to
        base (str): base icon (name or path)
        overlay (str): overlay icon (name or path)
        base_scale (float): apply scaling to base icon
        over_scale (float): apply scaling to overlay icon
        mode (str): where to store icon file
            Map File - use file as a map to a path in $TMP
            Simple File - simply use the file path

    Returns:
        (str): path to tmp icon
    """
    from pini import qt
    _LOGGER.debug('BUILD TMP ICON')

    # Get base pixmap
    _pix = to_pixmap(base)
    _pix = _pix.resize(144)
    if base_scale:
        _base = _pix
        _pix = qt.CPixmap(_base.size())
        _pix.fill('Transparent')
        _pix.draw_overlay(
            _base, pos=_pix.center(), size=_base.size() * base_scale,
            anchor='C')

    # Add overlay
    _over = to_pixmap(overlay)
    _over = _over.resize(144 * over_scale)
    _pix.draw_overlay(_over, pos=_pix.size(), anchor='BR')

    # Save file
    if mode == 'Map File':
        _tmp_fmt = build_cache_fmt(
            file_, tool='TmpIcons', extn='png', mode='home')
        _LOGGER.debug(' - TMP FMT %s', _tmp_fmt)
        _tmp_path = _tmp_fmt.format(func='icon')
    elif mode == 'Simple File':
        _tmp_path = file_
    else:
        raise ValueError(mode)
    _LOGGER.debug(' - TMP PATH %s', _tmp_path)
    _pix.save_as(_tmp_path, force=True, verbose=0)

    return _tmp_path


def close_all_interfaces(filter_=None):
    """Close all managed interfaces.

    Args:
        filter_ (str): filter list by stack key
    """
    _stack = sys.QT_DIALOG_STACK  # pylint: disable=no-member
    for _key, _dialog in list(_stack.items()):
        if filter_ and not passes_filter(_key, filter_):
            continue
        _dialog.delete()
        del _stack[_key]


def _pformat_widget(widget):
    """Format widget into a readable string.

    Args:
        widget (QWidget): widget to format

    Returns:
        (str): readable widget
    """
    _name = None
    if hasattr(widget, 'objectName'):
        _name = widget.objectName()
    _name = _name or id(widget)
    return basic_repr(widget, _name)


def find_widget_children(
        widget, indent='', filter_=None, class_=None, name=None):
    """Recursive function to find all children of the given widget.

    Args:
        widget (QWidget): widget to read
        indent (str): indent for logging
        filter_ (str): apply name filter (for debugging)
        class_ (class): apply widget type filter
        name (str): apply name filter

    Returns:
        (QWidget list): widget children
    """
    _LOGGER.debug(
        '%sFIND WIDGET CHILDREN %s', indent, _pformat_widget(widget))
    check_heart()

    if isinstance(widget, (QtWidgets.QSpacerItem,
                           QtWidgets.QListWidgetItem)):
        return []

    # Add widget children
    _children = []
    if hasattr(widget, 'children'):
        for _idx, _child in enumerate(widget.children()):
            _LOGGER.debug(
                '%s - %s ADDING CHILD %d %s', indent,
                _pformat_widget(widget), _idx, _child)
            _children += [_child] + find_widget_children(
                _child, indent=indent + '  ')
    _LOGGER.debug(
        '%s - %s FOUND %d CHILDREN', indent, _pformat_widget(widget),
        len(_children))

    # Apply filters
    _results = []
    for _widget in _children:
        _name = None
        if hasattr(_widget, 'objectName'):
            _name = _widget.objectName()
        if name and _name != name:
            continue
        if filter_ and (not _name or not passes_filter(_name, filter_)):
            continue
        if class_ and not isinstance(_widget, class_):
            continue
        _results.append(_widget)

    return _results


def flush_dialog_stack():
    """Empty dialog stack.

    This can be used as a last resort if closing all dialogs is failing because
    some dialogs are erroring on delete or save.
    """
    sys.QT_DIALOG_STACK = {}


@cache_result
def get_application(force=False):
    """Get QApplication instance.

    Args:
        force (bool): force re-wrap QCoreApplication if applicable

    Returns:
        (QApplication): application
    """
    _app = QtWidgets.QApplication.instance()
    if not _app:
        _app = QtWidgets.QApplication(sys.argv)

    # Wrap QCoreApplication
    if type(_app) is QtCore.QCoreApplication:  # pylint: disable=unidiomatic-typecheck
        _LOGGER.debug('FOUND QCoreApplication')
        if force or not hasattr(sys, 'PINI_WRAPPED_QAPPLICATION'):
            if LIB in ('PySide2', ):
                import shiboken2 as shiboken
            elif LIB in ('PySide6', ):
                import shiboken6 as shiboken
            else:
                raise NotImplementedError(LIB)
            _ptr = shiboken.getCppPointer(_app)[0]
            _app = shiboken.wrapInstance(_ptr, QtWidgets.QApplication)
            sys.PINI_WRAPPED_QAPPLICATION = _app
            _LOGGER.info('WRAPPED QCoreApplication')
        else:
            _app = sys.PINI_WRAPPED_QAPPLICATION

    return _app


def apply_emit(func):
    """Apply emit flag.

    Args:
        func (fn): method to decorate

    Returns:
        (fn): decorated method
    """

    def _emit_func(widget, *args, **kwargs):
        _blocked = widget.signalsBlocked()
        _emit = kwargs.get('emit', True)
        if _emit is not None:
            widget.blockSignals(True)
        _result = func(widget, *args, **kwargs)
        if _emit is not None:
            widget.blockSignals(_blocked)
        if _emit is True:
            _signal = widget_to_signal(widget)
            _args = []
            if isinstance(widget, QtWidgets.QTabWidget):
                _args = [widget.currentIndex()]
            _signal.emit(*_args)
        return _result

    return _emit_func


def nice_screen(screen):
    """Convert a screen name to a readable string.

    Args:
        screen (str): screen name

    Returns:
        (str): readable screen name
    """
    return screen.name().strip('/.\\')


@cache_result
def obt_icon(file_: str):
    """Obtain a cached version of the given icon.

    Args:
        file_ (str): path to icon

    Returns:
        (QIcon): icon
    """
    assert isinstance(file_, str)
    return to_icon(file_)


@cache_result
def obt_pixmap(file_: str):
    """Obtain a cached version of the given pixmap.

    ie. the image is only read from disk once

    Args:
        file_ (str): image to read - a string is required for cache efficiency

    Returns:
        (CPixmap): pixmap
    """
    if not isinstance(file_, str):
        raise RuntimeError(f'Bad type {file_} ({type(file_).__name__}')
    return to_pixmap(file_)


def p_is_onscreen(pos):
    """Check whether the given point is on a screen.

    Args:
        pos (QPoint): point to test

    Returns:
        (bool): whether pos is onscreen
    """
    _pos = to_p(pos)
    _screens = get_application().screens()
    _LOGGER.debug('   - SCREENS %s', _screens)
    _rects = [_screen.geometry() for _screen in _screens]
    _LOGGER.debug('   - RECTS %s', _rects)
    return bool([_rect for _rect in _rects if _rect.contains(_pos)])


def safe_timer_event(func):
    """Decorator to catch timer event errors caused by reloading.

    Args:
        func (fn): method to decorate

    Returns:
        (fn): decorated method
    """

    @functools.wraps(func)
    def _safe_timer_method(self, *args, **kwargs):

        _stop = False
        try:
            _result = func(self, *args, **kwargs)
        except TypeError as _exc:
            _LOGGER.info(' - TIMER FAILED %s', _exc)
            _stop = True

        check_logging_level()
        _LOGGER.log(
            9, 'SAFE TIMER EVENT %d vis=%d %s', _stop, self.isVisible(), self)

        _stop = _stop or not self.isVisible()
        if _stop:
            _LOGGER.debug(' - APPLY DELETE')
            self.delete()
            return None

        return _result

    return _safe_timer_method


def screen_is_available(screen):
    """Test whether the given screen is available.

    This is used to avoid loading settings from one screen to a different one,
    resulting in an interface being hidden or off-screen.

    Args:
        screen (str): name of screen to test

    Returns:
        (bool): whether screen is available
    """
    return screen in [
        nice_screen(_screen) for _screen in get_application().screens()]


def set_application_icon(icon, name=None):
    """Set current application icon.

    This also applies taskbar icon in windows. NOTE: to work, this code
    needs to be run before any window is made visible.

    Args:
        icon (str): path to icon to apply
        name (str): override application name
    """
    _LOGGER.info('SET APPLICATION ICON %s', icon)
    _icon = to_icon(icon)
    _LOGGER.info(' - ICON %s', _icon)

    _app = get_application()
    if os.name == 'nt':
        import ctypes
        _name = name or str(id(_app))
        _LOGGER.info(' - NAME %s', _name)
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(_name)
    _app.setWindowIcon(_icon)


def to_col(*args):
    """Map the given arg to a QColor object.

    eg. to_col("Red") -> Color(255, 0, 0)
        to_col(1.0, 0.0, 0.0) -> Color(255, 0, 0)
        to_col(255, 0, 0) -> Color(255, 0, 0)

    Returns:
        (QColor): colour
    """
    _LOGGER.log(9, 'TO COL %s', args)
    from pini import qt
    _args = args
    _arg = single(_args, catch=True)
    if isinstance(_arg, (list, tuple)):
        _args = _arg
        _arg = None
    if _arg:
        if isinstance(_arg, (qt.CColor, QtGui.QLinearGradient)):
            return _arg
        if isinstance(_arg, (str, QtGui.QColor)):
            return qt.CColor(_arg)
    if len(_args) in (3, 4):
        if (
                any(_arg for _arg in _args if isinstance(_arg, float)) and
                max(_args) <= 1.0):
            _LOGGER.debug(' - ASSUMING RGBF')
            return qt.CColor.fromRgbF(*_args)
        if _args[0] <= 256:
            return qt.CColor(*_args)
    raise ValueError(args)


def to_font(obj):
    """Obtain a font from the given object.

    Args:
        obj (any): font name (eg. Arial) or font

    Returns:
        (QFont|None): font (if available)
    """
    if isinstance(obj, QtGui.QFont):
        return obj
    if obj not in QtGui.QFontDatabase().families():
        return QtGui.QFont()
    return QtGui.QFont(obj)


def to_icon(arg):
    """Obtain QIcon from given argument.

    Args:
        arg (any): argument to convert

    Returns:
        (QIcon): icon
    """
    _arg = arg
    if isinstance(_arg, QtGui.QIcon):
        return _arg
    if isinstance(_arg, (str, File)):
        _arg = to_pixmap(_arg)
    return QtGui.QIcon(_arg)


def to_p(*args, **kwargs):
    """Obtain a point object from the given argument.

    Returns:
        (QPoint): point
    """
    _LOGGER.log(9, 'TO P %s', args)

    _class = kwargs.pop('class_', None)
    _LOGGER.log(9, ' - CLASS %s', _class)
    if kwargs:
        raise TypeError(kwargs)

    _arg = single(args, catch=True)
    _LOGGER.log(9, ' - ARG %s (%s) %d', _arg, args, len(args))

    # Handle arg
    if _arg is not None:
        _result = _arg_to_p(_arg)
    else:
        _LOGGER.log(9, ' - ARGS %s', args)
        if (  # Floats tuple
                len(args) == 2 and (
                    isinstance(args[0], float) or
                    isinstance(args[1], float))):
            _result = QtCore.QPointF(*args)
        elif (  # Ints tuple
                len(args) == 2 and
                isinstance(args[0], int) and
                isinstance(args[1], int)):
            _result = QtCore.QPoint(*args)
        else:
            raise ValueError(args)

    if _class:
        _LOGGER.log(9, ' - CASTING RESULT %s', _result)
        _result = _class(_result)
        _LOGGER.log(9, ' - RESULT %s', _result)

    return _result


def _arg_to_p(arg):
    """Obtain point from single arg.

    Args:
        arg (any): arg to convert

    Returns:
        (QPoint|QPointF): point
    """
    if isinstance(arg, (QtCore.QPoint, QtCore.QPointF)):
        _result = arg
    elif isinstance(arg, QtCore.QSize):
        _result = QtCore.QPoint(arg.width(), arg.height())
    elif isinstance(arg, QtCore.QSizeF):
        _result = QtCore.QPointF(arg.width(), arg.height())
    elif isinstance(arg, (tuple, list)) and len(arg) == 2:
        _result = to_p(*arg)
    elif isinstance(arg, int):
        _result = QtCore.QPoint(arg, arg)
    elif isinstance(arg, QtGui.QVector2D):
        _result = QtCore.QPointF(arg.x(), arg.y())
    else:
        raise ValueError(arg)

    return _result


def to_pixmap(arg):
    """Obtain a pixmap object from the given argument.

    Args:
        arg (any): arg to check

    Returns:
        (CPixmap): pixmap
    """
    from pini import qt
    qt.get_application()
    if isinstance(arg, qt.CPixmap):
        return arg
    if isinstance(arg, File):
        return qt.CPixmap(arg.path)
    return qt.CPixmap(arg)


def to_rect(pos=(0, 0), size=(640, 640), anchor='TL', class_=None):  # pylint: disable=too-many-branches
    """Build a QRect object based on the args provided.

    Args:
        pos (QPoint): position
        size (QSize): size
        anchor (str): anchor position
        class_ (class): override rect class

    Returns:
        (QRect|QRectF): region
    """
    from pini import qt

    _LOGGER.debug('TO RECT %s %s', pos, size)
    _size = to_size(size)
    _use_int = not isinstance(_size, QtCore.QSizeF)
    _LOGGER.debug(' - SIZE %s', _size)
    _class = qt.CPointF if not _use_int else None
    _pos = to_p(pos, class_=_class)
    _LOGGER.debug(' - POS %s', _pos)

    # Determine root position (top left) of result
    if anchor == 'C':
        _root = _pos - to_p(_size) / 2
    elif anchor == 'L':
        _root_y = _size.height() / 2
        if _use_int:
            _root_y = round(_root_y)
        _root = _pos - to_p(0, _root_y)
    elif anchor == 'R':
        _root_y = _size.height() / 2
        if _use_int:
            _root_y = round(_root_y)
        _root = _pos - to_p(_size.width(), _root_y)
    elif anchor == 'T':
        _root = _pos - to_p(_size.width() / 2, 0)
    elif anchor == 'TL':
        _root = _pos
    elif anchor == 'TR':
        _root = _pos - to_p(_size.width(), 0)
    elif anchor == 'BL':
        _root = _pos - to_p(0, _size.height())
    elif anchor == 'BR':
        _root = _pos - to_p(_size.width(), _size.height())
    elif anchor == 'B':
        _root = _pos - to_p(_size.width() / 2, _size.height())
    else:
        raise ValueError(anchor)

    # Determine class of result
    _class = class_
    if not _class:
        if (
                isinstance(_root, QtCore.QPointF) or
                isinstance(_size, QtCore.QSizeF)):
            _class = qt.CRectF
        else:
            _class = qt.CRect

    return _class(_root, _size)


def to_size(*args, **kwargs):  # pylint: disable=too-many-branches
    """Obtain a size object from the given args/kwargs.

    Returns:
        (QSize): size
    """
    _LOGGER.log(9, 'TO SIZE %s %s', args, kwargs)

    # Calculate result
    if len(args) == 1:
        _size = single(args)
        _LOGGER.log(9, ' - SIZE %s', _size)
        if isinstance(_size, QtCore.QSize):
            _result = _size
        elif isinstance(_size, QtCore.QSizeF):
            _result = _size
        elif isinstance(_size, QtCore.QPoint):
            _result = QtCore.QSize(_size.x(), _size.y())
        elif isinstance(_size, QtCore.QPointF):
            _result = QtCore.QSizeF(_size.x(), _size.y())
        elif isinstance(_size, QtGui.QVector2D):
            _result = QtCore.QSizeF(abs(_size.x()), abs(_size.y()))
        elif isinstance(_size, (tuple, list)) and len(_size) == 2:
            _class = (QtCore.QSizeF if isinstance(_size[0], float)
                      else QtCore.QSize)
            _result = _class(_size[0], _size[1])
        elif isinstance(_size, str):
            _result = QtCore.QSize(*[
                int(_token) for _token in _size.split('x')])
        elif isinstance(_size, int):
            _result = QtCore.QSize(_size, _size)
        elif isinstance(_size, float):
            _result = QtCore.QSizeF(_size, _size)
        else:
            raise ValueError(args)
    elif len(args) == 2:
        _class = QtCore.QSizeF if isinstance(args[0], float) else QtCore.QSize
        _result = _class(*args)
    else:
        raise ValueError(args)

    # Apply typecasting
    _class = kwargs.get('class_')
    if _class:
        _LOGGER.log(9, ' - APPLY TYPECASTING %s %s', _class, _result)
        if (
                issubclass(_class, QtCore.QSize) and
                isinstance(_result, QtCore.QSize)):
            _result = _class(round(_result.width()), round(_result.height()))
        elif (
                issubclass(_class, (QtCore.QSize, QtCore.QSizeF)) and
                isinstance(_result, (QtCore.QSize, QtCore.QSizeF))):
            _result = _class(_result.width(), _result.height())
        else:
            raise NotImplementedError(_class)

    return _result


def widget_to_signal(widget):  # pylint: disable=too-many-branches
    """Obtain the value changed signal for the given widget.

    This is used to connect callbacks to.

    Args:
        widget (QWidget): widget to obtain signal for

    Returns:
        (QSignal): signal
    """
    _signal = None
    if isinstance(widget, QtWidgets.QCheckBox):
        _signal = widget.toggled
    elif isinstance(widget, QtWidgets.QComboBox):
        _signal = widget.currentTextChanged
    elif isinstance(widget, QtWidgets.QLineEdit):
        _signal = widget.textChanged
    elif isinstance(widget, QtWidgets.QListWidget):
        _signal = widget.itemSelectionChanged
    elif isinstance(widget, QtWidgets.QPushButton):
        if widget.isCheckable():
            _signal = widget.toggled
        else:
            _signal = widget.clicked
    elif isinstance(widget, QtWidgets.QSlider):
        _signal = widget.valueChanged
    elif isinstance(widget, QtWidgets.QSpinBox):
        _signal = widget.valueChanged
    elif isinstance(widget, QtWidgets.QTabWidget):
        _signal = widget.currentChanged
    elif isinstance(widget, QtWidgets.QTextEdit):
        _signal = widget.textChanged
    elif isinstance(widget, QtWidgets.QTreeWidget):
        _signal = widget.itemSelectionChanged

    # Special cases
    elif isinstance(widget, QtWidgets.QListView):
        # Needs to be after QListWidget as QListWidget is
        # instance of QListView
        _model = widget.selectionModel()
        if _model:
            _signal = _model.selectionChanged
    elif isinstance(widget, (QtWidgets.QLabel,
                             QtWidgets.QFrame,
                             QtWidgets.QSpacerItem)):
        # These at the end otherwise some other elements get caught (?)
        pass
    else:
        raise NotImplementedError(widget)

    return _signal
