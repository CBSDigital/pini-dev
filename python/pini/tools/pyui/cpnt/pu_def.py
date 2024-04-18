"""Tools for managing pyui functions."""

# pylint: disable=too-many-instance-attributes

import functools
import inspect
import logging

from pini import icons
from pini.tools import usage, error
from pini.utils import abs_path, str_to_seed, to_nice, basic_repr

from . import pu_arg

_LOGGER = logging.getLogger(__name__)


class PUDef(object):
    """Decorator which wraps a function and allows metadata to be added."""

    pyui_file = None  # Applied on build ui
    py_def = None  # Can be applied on build ui

    def __init__(
            self, func, py_def=None, icon=None, label=None, clear=(),
            browser=(), hide=(), choices=None):
        """Constructor.

        Args:
            func (fn): function to wrap
            py_def (PyDef): corresponding PyFile def
            icon (str): icon to display (otherwise random fruit is allocated)
            label (str): override function label (otherwise the function
                name is used in a readable form)
            clear (tuple): args to apply clear button to
            browser (tuple|dict): args to apply browser to
            hide (tuple): args to hide from ui
            choices (dict): arg/opts data for option lists
        """
        self.func = func
        self.py_def = py_def
        self.icon = icon or _func_to_icon(func)
        self.label = label or to_nice(func.__name__).capitalize()

        self.clear = clear
        self.browser = browser
        self.hide = hide
        self.choices = choices or {}

        self.name = func.__name__

        functools.update_wrapper(self, func)

    def to_args(self):
        """Read this functions args.

        Returns:
            (PUArg list): args
        """
        _args = []
        for _py_arg in self.py_def.find_args():
            _name = _py_arg.name
            if _name not in self.browser:
                _browser = False
            elif isinstance(self.browser, dict):
                _browser = self.browser.get(_name, False)
            else:
                _browser = _name in self.browser
            if _name in self.hide:
                continue
            _arg = pu_arg.PUArg(
                _name, py_arg=_py_arg, clear=_name in self.clear,
                browser=_browser, py_def=self.py_def, pyui_file=self.pyui_file,
                choices=self.choices.get(_name))
            _args.append(_arg)

        return _args

    def __call__(self, *args, **kwargs):
        _func = self.func
        _func = usage.track(_func)
        _func = error.catch(_func)
        return _func(*args, **kwargs)

    def __repr__(self):
        return basic_repr(self, self.name)


def _func_to_icon(func):
    """Map a function to a random icon, using the name and file as a key.

    Args:
        func (fn): function to map

    Returns:
        (str): path to icon
    """
    _path = abs_path(inspect.getfile(func))
    _LOGGER.debug(' - FUNC TO ICON %s', _path)
    _, _rel_path = _path.rsplit('/python/', 1)
    _uid = '{}.{}'.format(_rel_path, func.__name__)
    _rand = str_to_seed(_uid)
    return _rand.choice(icons.FRUIT)
