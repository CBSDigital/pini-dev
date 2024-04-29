"""Tools for managing pyui functions."""

# pylint: disable=too-many-instance-attributes

import functools
import inspect
import logging

from pini import icons
from pini.tools import usage, error
from pini.utils import abs_path, str_to_seed, to_nice, basic_repr, single

from . import pu_arg

_LOGGER = logging.getLogger(__name__)


class PUDef(object):
    """Decorator which wraps a function and allows metadata to be added."""

    pyui_file = None  # Applied on build ui
    py_def = None  # Can be applied on build ui

    def __init__(
            self, func, py_def=None, icon=None, label=None, clear=(),
            browser=(), hide=(), selection=(), choices=None, col=None,
            label_w=None):
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
            selection (tuple|dict): arg to apply get selected node to
            choices (dict): arg/opts data for option lists
            col (str|QColor): override def colour
            label_w (int): override label width (in pixels)
        """
        self.func = func
        self.py_def = py_def
        self.icon = icon or _func_to_icon(func)
        self.label = label or to_nice(func.__name__).capitalize()

        self.clear = clear
        self.browser = browser
        self.selection = selection
        self.hide = hide
        self.choices = choices or {}

        self.col = col
        self.label_w = label_w

        self.name = func.__name__

        functools.update_wrapper(self, func)

    @property
    def uid(self):
        """Obtain uid for this function.

        Returns:
            (str): uid
        """
        return self.py_def.name

    def find_arg(self, match=None):
        """Find one of this function's arguments.

        Args:
            match (str): match by name

        Returns:
            (PUArg): matching argument
        """
        _args = self.find_args()
        if len(_args) == 1:
            return single(_args)
        _match_args = [_arg for _arg in _args if match in (_arg.name, )]
        if len(_match_args) == 1:
            return single(_match_args)
        raise ValueError(match)

    def find_args(self):
        """Read this functions args.

        Returns:
            (PUArg list): args
        """
        _args = []
        for _py_arg in self.py_def.find_args():

            _name = _py_arg.name

            _docs = _py_arg.to_docs('SingleLine') or ''
            _docs = _docs.capitalize()

            # Determine browser setting
            if _name not in self.browser:
                _browser = False
            elif isinstance(self.browser, dict):
                _browser = self.browser.get(_name, False)
            else:
                _browser = _name in self.browser

            # Determine selection setting
            if _name not in self.selection:
                _selection = False
            elif isinstance(self.selection, dict):
                _selection = self.selection.get(_name, False)
            else:
                _selection = _name in self.selection

            if _name in self.hide:
                continue

            # Build arg
            _arg = pu_arg.PUArg(
                _name, py_arg=_py_arg, clear=_name in self.clear,
                browser=_browser, py_def=self.py_def, pyui_file=self.pyui_file,
                choices=self.choices.get(_name), label_w=self.label_w,
                selection=_selection, docs=_docs)
            _args.append(_arg)

        return _args

    def __call__(self, *args, **kwargs):
        _func = self.func
        _tracker = usage.get_tracker(args=list(kwargs.keys()))
        _func = _tracker(_func)
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
    for _splitter in ['/python/', '/scripts/']:
        if _splitter in _path:
            _, _rel_path = _path.rsplit(_splitter, 1)
            break
    else:
        raise RuntimeError(func, _path)
    _uid = '{}.{}'.format(_rel_path, func.__name__)
    _rand = str_to_seed(_uid)
    return _rand.choice(icons.FRUIT)
