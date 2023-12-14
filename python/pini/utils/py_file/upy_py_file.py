"""Tools for managing the PyFile object."""

import ast
import inspect
import logging
import sys

from ..path import File, Dir
from .upy_elem import PyElem

_LOGGER = logging.getLogger(__name__)


class PyFile(File, PyElem):
    """Represents a python file on disk."""

    def __init__(self, file_):
        """Constructor.

        Args:
            file_ (str): path to py file
        """
        super(PyFile, self).__init__(file_)

        if self.extn == 'pyc':
            super(PyFile, self).__init__(self.to_file(extn='py'))
        if self.extn != 'py':
            raise ValueError(self.extn)

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
        if catch:
            try:
                return ast.parse(self.read())
            except Exception as _exc:  # pylint: disable=broad-except
                _LOGGER.error('READ FILE FAILED %s', self.path)
                return None
        return ast.parse(self.read())

    def to_module(self, reload_=False, catch=False):
        """Obtain the module for this py file.

        Args:
            reload_ (bool): reload module
            catch (bool): no error if module fails to import

        Returns:
            (mod): module
        """
        from pini.utils import six_reload

        # Find module name
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
        _mod_name = _tokens.replace('/', '.')

        # Import module
        try:
            _mod = __import__(_mod_name, fromlist=_mod_name.split())
        except Exception as _exc:
            if catch:
                return None
            raise _exc

        if reload_:
            six_reload(_mod)

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
