"""General qt utilities."""

import functools
import logging
import os
import sys

import six

from pini.utils import (
    cache_result, single, HOME_PATH, passes_filter, check_heart, SixIntEnum,
    basic_repr, File)

from .q_mgr import QtWidgets, QtCore, QtGui

_LOGGER = logging.getLogger(__name__)
SETTINGS_DIR = '{}/.pini/settings'.format(HOME_PATH)

X_AXIS = QtCore.QPoint(1, 0)
Y_AXIS = QtCore.QPoint(0, 1)


class DialogCancelled(RuntimeError):
    """Raise on dialog cancelled."""


class SavePolicy(SixIntEnum):
    """Enum to manage widget save policy options."""

    DEFAULT = 0
    NO_SAVE = 1
    SAVE_ON_CHANGE = 2


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


def find_widget_children(widget, indent=''):
    """Recursive function to find all children of the given widget.

    Args:
        widget (QWidget): widget to read
        indent (str): indent for logging

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
                _child, indent=indent+'  ')
    _LOGGER.debug(
        '%s - %s FOUND %d CHILDREN', indent, _pformat_widget(widget),
        len(_children))

    return _children


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
    if type(_app) is QtCore.QCoreApplication:  # pylint: disable=unidiomatic-typecheck
        _LOGGER.debug('FOUND QCoreApplication')
        if force or not hasattr(sys, 'PINI_WRAPPED_QAPPLICATION'):
            import shiboken2
            _ptr = shiboken2.getCppPointer(_app)[0]
            _app = shiboken2.wrapInstance(_ptr, QtWidgets.QApplication)
            sys.PINI_WRAPPED_QAPPLICATION = _app
            _LOGGER.info('WRAPPED QCoreApplication')
        else:
            _app = sys.PINI_WRAPPED_QAPPLICATION
    return _app


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
            _stop = True

        _stop = _stop or not self.isVisible()
        if _stop:
            self.delete()
            return None

        return _result

    return _safe_timer_method


def set_application_icon(icon, name=None):
    """Set current application icon.

    This also applies taskbar icon in windows. NOTE: to work, this code
    needs to be run before any window is made visible.

    Args:
        icon (str): path to icon to apply
        name (str): override application name
    """
    _icon = to_icon(icon)

    _app = get_application()
    if os.name == 'nt':
        import ctypes
        _name = name or str(id(_app))
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
    _LOGGER.debug('TO COL %s', args)
    from pini import qt
    _args = args
    _arg = single(_args, catch=True)
    if isinstance(_arg, (list, tuple)):
        _args = _arg
        _arg = None
    if _arg:
        if isinstance(_arg, (qt.CColor, QtGui.QLinearGradient)):
            return _arg
        if isinstance(_arg, (six.string_types, QtGui.QColor)):
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


def to_font(name):
    """Obtain a font of the given name.

    Args:
        name (str): font name (eg. Arial)

    Returns:
        (QFont|None): font (if available)
    """
    if name not in QtGui.QFontDatabase().families():
        return None
    return QtGui.QFont(name)


def to_icon(arg):
    """Obtain QIcon from given argument.

    Args:
        arg (any): argument to convert

    Returns:
        (QIcon): icon
    """
    if isinstance(arg, QtGui.QIcon):
        return arg
    return QtGui.QIcon(arg)


def to_p(*args, **kwargs):
    """Obtain a point object from the given argument.

    Returns:
        (QPoint): point
    """
    _LOGGER.debug('TO P %s', args)

    _class = kwargs.pop('class_', None)
    if kwargs:
        raise TypeError(kwargs)
    _LOGGER.debug(' - CLASS %s', _class)

    _arg = single(args, catch=True)

    if isinstance(_arg, (QtCore.QPoint, QtCore.QPointF)):
        _result = _arg
    elif isinstance(_arg, (QtCore.QSize, QtCore.QSizeF)):
        _result = QtCore.QPoint(_arg.width(), _arg.height())
    elif isinstance(_arg, (tuple, list)):
        _result = QtCore.QPoint(*_arg)
    elif isinstance(_arg, int):
        _result = QtCore.QPoint(_arg, _arg)
    elif (  # Ints tuple
            len(args) == 2 and
            isinstance(args[0], int) and
            isinstance(args[1], int)):
        _result = QtCore.QPoint(*args)
    elif (  # Floats tuple
            len(args) == 2 and
            isinstance(args[0], float) and
            isinstance(args[1], float)):
        _result = QtCore.QPointF(*args)
    elif isinstance(_arg, QtGui.QVector2D):
        _result = QtCore.QPointF(_arg.x(), _arg.y())
    else:
        _result = QtCore.QPoint(*args)

    if _class:
        _result = _class(_result)

    return _result


def to_pixmap(arg):
    """Obtain a pixmap object from the given argument.

    Args:
        arg (any): arg to check

    Returns:
        (CPixmap): pixmap
    """
    from pini import qt
    if isinstance(arg, qt.CPixmap):
        return arg
    if isinstance(arg, File):
        return qt.CPixmap(arg.path)
    return qt.CPixmap(arg)


def to_rect(pos=(0, 0), size=(640, 640), anchor='TL'):
    """Build a QRect object based on the args provided.

    Args:
        pos (QPoint): position
        size (QSize): size
        anchor (str): anchor position

    Returns:
        (QRect): region
    """
    _size = to_size(size)
    _pos = to_p(pos)

    if anchor == 'C':
        _root = _pos - to_p(_size)/2
    elif anchor == 'L':
        _root = _pos - to_p(0, _size.height()/2)
    elif anchor == 'R':
        _root = _pos - to_p(_size.width(), _size.height()/2)
    elif anchor == 'T':
        _root = _pos - to_p(_size.width()/2, 0)
    elif anchor == 'TL':
        _root = _pos
    elif anchor == 'TR':
        _root = _pos - to_p(_size.width(), 0)
    elif anchor == 'BL':
        _root = _pos - to_p(0, _size.height())
    elif anchor == 'BR':
        _root = _pos - to_p(_size.width(), _size.height())
    elif anchor == 'B':
        _root = _pos - to_p(_size.width()/2, _size.height())
    else:
        raise ValueError(anchor)

    if isinstance(_root, QtCore.QPointF) or isinstance(_size, QtCore.QSizeF):
        return QtCore.QRectF(_root, _size)

    return QtCore.QRect(_root, _size)


def to_size(*args, **kwargs):  # pylint: disable=too-many-branches
    """Obtain a size object from the given args/kwargs.

    Returns:
        (QSize): size
    """

    # Calculate result
    if len(args) == 1:
        _size = single(args)
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
        elif isinstance(_size, (tuple, list)):
            _result = QtCore.QSize(_size[0], _size[1])
        elif isinstance(_size, six.string_types):
            _result = QtCore.QSize(*[
                int(_token) for _token in _size.split('x')])
        elif isinstance(_size, int):
            _result = QtCore.QSize(_size, _size)
        elif isinstance(_size, float):
            _result = QtCore.QSizeF(_size, _size)
        else:
            raise ValueError(args)
    elif len(args) == 2:
        _result = QtCore.QSize(*args)
    else:
        raise ValueError(args)

    # Apply typecasting
    _class = kwargs.get('class_')
    if _class:
        if (
                issubclass(_class, QtCore.QSize) and
                isinstance(_result, QtCore.QSize)):
            _result = _class(int(_result.width()), int(_result.height()))
        elif (
                issubclass(_class, QtCore.QSize) and
                isinstance(_result, QtCore.QSizeF)):
            _result = _class(int(_result.width()), int(_result.height()))
        else:
            raise NotImplementedError

    return _result


def widget_to_signal(widget):  # pylint: disable=too-many-branches
    """Obtain the value changed signal for the given widget.

    This is used to connect callbacks to.

    Args:
        widget (QWidget): widget to obtain signal for

    Returns:
        (QSignal): signal
    """

    if isinstance(widget, QtWidgets.QCheckBox):
        _signal = widget.toggled
    elif isinstance(widget, QtWidgets.QComboBox):
        _signal = widget.currentTextChanged
    elif isinstance(widget, QtWidgets.QLineEdit):
        _signal = widget.textChanged
    elif isinstance(widget, QtWidgets.QListWidget):
        _signal = widget.itemSelectionChanged
    elif isinstance(widget, QtWidgets.QPushButton):
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
        return None

    else:
        raise NotImplementedError(widget)

    return _signal
