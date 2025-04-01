"""Tools for managing the PyFile object."""

import ast
import inspect
import logging
import importlib
import sys

from ..path import File, Dir
from .upy_elem import PyElem

_LOGGER = logging.getLogger(__name__)


class PyFile(File, PyElem):
    """Represents a python file on disk."""

    def __init__(self, file_, check_extn=True):
        """Constructor.

        Args:
            file_ (str): path to py file
            check_extn (bool): apply extension test
        """
        _file = File(file_)
        if _file.extn == 'pyc':
            _file = self.to_file(extn='py')
        super().__init__(_file.path)

        if check_extn and self.extn != 'py':
            raise ValueError(f'Bad extn: {self.path}')

    @property
    def py_file(self):
        """Obtain associated python file (ie. this file).

        Provided for PyElem symmetry.

        Returns:
            (PyFile): py file
        """
        return self

    def to_ast(self, catch=False):
        """Obtain ast for this py file.

        Args:
            catch (bool): no error if fail to parse python

        Returns:
            (Module): ast module
        """
        _LOGGER.debug('TO AST %s', self)
        if catch:
            try:
                return ast.parse(self.read())
            except Exception as _exc:  # pylint: disable=broad-except
                _LOGGER.error('READ FILE FAILED %s', self.path)
                return None

        _body = self.read()
        try:
            _ast = ast.parse(_body)
        except SyntaxError as _exc:
            from pini.tools import error
            _LOGGER.debug(' - SYNTAX ERROR %s', self)
            _line_n = int(str(_exc).split()[-1].strip(')'))
            _LOGGER.debug(' - LINE N %s', _line_n)
            raise error.FileError(
                f'Syntax error at line {_line_n:d} in {self}',
                file_=self, line_n=_line_n)
        return _ast

    def to_module_name(self):
        """Obtain module name for this python file.

        eg. ~/dev/pini-dev/python/pini/utils/u_misc.py -> pini.utils.u_misc

        Returns:
            (str): module name
        """
        if '/python/' in self.path:
            _, _rel_path = self.path.rsplit('/python/', 1)
        elif '/startup/' in self.path:
            _, _rel_path = self.path.rsplit('/startup/', 1)
        elif _find_sys_path(self.path):
            _sys_path = _find_sys_path(self.path)
            _rel_path = _sys_path.rel_path(self.path)
        else:
            raise NotImplementedError(self.path)
        _tokens, _ = _rel_path.split('.')

        return _tokens.replace('/', '.')

    def to_module(self, reload_=False, catch=False):
        """Obtain the module for this py file.

        Args:
            reload_ (bool): reload module
            catch (bool): no error if module fails to import

        Returns:
            (mod): module
        """
        _mod_name = self.to_module_name()

        # Import module
        try:
            _mod = __import__(_mod_name, fromlist=_mod_name.split())
        except Exception as _exc:
            if catch:
                return None
            raise _exc

        if reload_:
            importlib.reload(_mod)

        return _mod


def _find_sys_path(path):
    """Find dir in sys.path that contains the given path.

    Args:
        path (str): path to check for

    Returns:
        (Dir|None): sys.path path (if any)
    """
    for _path in sys.path:
        _path = Dir(_path)
        if _path.contains(path):
            return _path
    return None


def to_py_file(obj):
    """Map the given object to a PyFile.

    Args:
        obj (any): object to convert

    Returns:
        (PyFile): py file
    """
    if inspect.ismodule(obj):
        return PyFile(obj.__file__.replace('.pyc', '.py'))
    raise ValueError(obj)
