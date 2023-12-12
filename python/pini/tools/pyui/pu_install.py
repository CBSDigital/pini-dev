"""Tools for managing the pyui install decorator.

This allows pyui metadata to be applied to function definitions which
are to be built into an interface.
"""

import functools
import inspect

from pini import icons
from pini.tools import error, usage
from pini.utils import abs_path, str_to_seed, to_nice, basic_repr


class PyUiFunc(object):
    """Decorator which wraps a function and allows metadata to be added."""

    def __init__(self, func, icon=None, label=None):
        """Constructor.

        Args:
            func (fn): function to wrap
            icon (str): icon to display (otherwise random fruit is allocated)
            label (str): override function label (otherwise the function
                name is used in a readable form)
        """
        self.func = func
        self.icon = icon or _func_to_icon(func)
        self.label = label or to_nice(func.__name__).capitalize()
        functools.update_wrapper(self, func)

    def __call__(self, *args, **kwargs):
        _func = self.func
        _func = usage.track(_func)
        _func = error.catch(_func)
        return _func(*args, **kwargs)

    def __repr__(self):
        return basic_repr(self, self.label)


def _func_to_icon(func):
    """Map a function to a random icon, using the name and file as a key.

    Args:
        func (fn): function to map

    Returns:
        (str): path to icon
    """
    _path = abs_path(inspect.getfile(func))
    _, _rel_path = _path.rsplit('/python/', 1)
    _uid = '{}.{}'.format(_rel_path, func.__name__)
    _rand = str_to_seed(_uid)
    return _rand.choice(icons.FRUIT)


def install(label=None, icon=None):
    """Builds a decorator which allows metadata to be added to a function.

    Args:
        label (str): override function label
        icon (str): override path to function icon

    Returns:
        (fn): decorator
    """
    def _build_pyui_dec(func):
        _dec = PyUiFunc(func, label=label, icon=icon)
        return _dec
    return _build_pyui_dec


def to_pyui_func(func):
    """Obtain a PyUiFunc object for the given function.

    If the function is already wrapped, the function is just returned.
    Otherwise the function is wrapped using default values.

    Args:
        func (fn): function to convert

    Returns:
        (PyUiFunc): wrapped function
    """
    _func = func
    if not isinstance(_func, PyUiFunc):
        _func = PyUiFunc(_func)
    return _func
