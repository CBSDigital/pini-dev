"""Tools for managing py defs, ie. function definitions in a python file."""

import ast
import logging
import sys

from ..u_misc import safe_zip, single
from .upy_elem import PyElem

_LOGGER = logging.getLogger(__name__)

_AstNoneType = ast.Name
if sys.version_info.major == 3:
    _AstNoneType = ast.NameConstant


class PyDef(PyElem):
    """Represents a python definition."""

    def execute(self, *args, **kwargs):
        """Execute this function, passing the given args/kwargs.

        Returns:
            (any): function result
        """
        return self.to_func(*args, **kwargs)

    @property
    def args(self):
        """Obtain args list.

        Returns:
            (PyArg tuple): args
        """
        return tuple(self.find_args())

    def find_arg(self, name):
        """Find an arg from this def.

        Args:
            name (str): arg name

        Returns:
            (PyArg): matching arg
        """
        return single([_arg for _arg in self.find_args()
                       if _arg.name == name])

    def find_args(self):
        """Find args of this def.

        Returns:
            (PyArg list): args
        """
        from pini.utils import PyArg
        _LOGGER.debug('FIND ARGS %s', self)

        _n_args = len(self._ast.args.args) - len(self._ast.args.defaults)
        _ast_args = self._ast.args.args[:_n_args]
        _ast_kwargs = self._ast.args.args[_n_args:]

        _args = []

        # Add args
        for _ast_arg in _ast_args:
            _arg = PyArg(_ast_arg_to_name(_ast_arg))
            _args.append(_arg)

        # Add kwargs
        for _ast_arg, _ast_default in safe_zip(
                _ast_kwargs, self._ast.args.defaults):
            _name = _ast_arg_to_name(_ast_arg)
            _LOGGER.debug(
                ' - ADDING KWARG %s %s %s', _name, _ast_arg, _ast_default)
            if isinstance(_ast_default, ast.Num):
                _default = _ast_default.n
            elif isinstance(_ast_default, ast.Str):
                _default = _ast_default.s
            elif isinstance(_ast_default, (ast.Name, ast.Call, _AstNoneType)):
                _default = None
            else:
                raise ValueError(_ast_default)
            _arg = PyArg(_name, default=_default)
            _args.append(_arg)

        return _args

    def to_func(self):
        """Obtain this def's fuction.

        This attempts to import the module and the obtain the attibute
        matching this def.

        Returns:
            (fn): function
        """
        _mod = self.py_file.to_module()
        return getattr(_mod, self.name)


def _ast_arg_to_name(arg):
    """Obtain name for ast arg object.

    To handle changed naming between py2/3.

    Args:
        arg (Name): ast arg object

    Returns:
        (str): arg name
    """
    if sys.version_info.major == 2:
        return arg.id
    if sys.version_info.major == 3:
        return arg.arg
    raise ValueError(sys.version_info.major)
