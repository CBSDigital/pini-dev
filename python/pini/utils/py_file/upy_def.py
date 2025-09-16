"""Tools for managing py defs, ie. function definitions in a python file."""

import ast
import importlib
import logging
import sys

from ..u_heart import check_heart
from ..u_misc import safe_zip, single
from . import upy_elem, upy_docs

_LOGGER = logging.getLogger(__name__)

_AstNoneType = ast.Name
if sys.version_info.major == 3:
    _AstNoneType = ast.NameConstant


class PyDef(upy_elem.PyElem):
    """Represents a python definition."""

    def execute(self, *args, **kwargs):
        """Execute this function, passing the given args/kwargs.

        Returns:
            (any): function result
        """
        return self.to_func()(*args, **kwargs)

    @property
    def args(self):
        """Obtain args list.

        Returns:
            (PyArg tuple): args
        """
        return tuple(self.find_args())

    def find_arg(self, name, args: ast.arguments=None, catch=False):
        """Find an arg from this def.

        Args:
            name (str): arg name
            args (arguments): override args object to read from
            catch (bool): no error of no arg found

        Returns:
            (PyArg): matching arg
        """
        _args = self.find_args(args=args)
        return single(
            [_arg for _arg in _args if _arg.name == name],
            catch=catch)

    def find_args(self, args: ast.arguments=None):
        """Find args of this def.

        Args:
            args (arguments): override args object to read from

        Returns:
            (PyArg list): args
        """
        from pini.utils import PyArg
        _LOGGER.debug('FIND ARGS %s', self)
        _args = args or self._ast.args
        assert isinstance(_args, ast.arguments)

        _n_args = len(_args.args) - len(_args.defaults)
        _ast_args = _args.args[:_n_args]
        _ast_kwargs = _args.args[_n_args:]

        _py_args = []

        # Add args
        for _ast_arg in _ast_args:
            _arg = PyArg(
                _ast_arg_to_name(_ast_arg), parent=self, has_default=False)
            _py_args.append(_arg)

        # Add kwargs
        for _ast_arg, _ast_default in safe_zip(
                _ast_kwargs, _args.defaults):
            _name = _ast_arg_to_name(_ast_arg)
            _LOGGER.debug(
                ' - ADDING KWARG %s %s', _name, _ast_arg)
            _LOGGER.debug('   - AST DEFAULT %s', _ast_default)
            if isinstance(_ast_default, ast.Num):
                _default = _ast_default.n
            elif isinstance(_ast_default, ast.Str):
                _default = _ast_default.s
            elif isinstance(_ast_default, ast.Constant):  # bool
                _default = _ast_default.n
            elif isinstance(_ast_default, ast.Tuple):
                _default = tuple(_item.s for _item in _ast_default.dims)
            elif isinstance(_ast_default, (
                    ast.Name, ast.Call, ast.UnaryOp, _AstNoneType)):
                _default = None
            elif isinstance(_ast_default, ast.Attribute):
                _default = _ast_attr_to_val(_ast_default, catch=True)
            else:
                raise ValueError(_ast_default)
            _LOGGER.debug('   - DEFAULT %s', _default)
            _arg = PyArg(_name, default=_default, parent=self, has_default=True)
            _LOGGER.debug('   - ARG %s type=%s', _arg, _arg.type_)
            _py_args.append(_arg)

        return _py_args

    def to_func(self):
        """Obtain this def's fuction.

        This attempts to import the module and the obtain the attibute
        matching this def.

        Returns:
            (fn): function
        """
        _mod = self.py_file.to_module()
        return getattr(_mod, self.name)

    def to_docs(self, mode='Object'):
        """Obtain documentation for this function.

        Args:
            mode (str): type of data to retrive
                Object - docs object containing all data
                Header - docs as string exculding args/results
                Title - first line of docs

        Returns:
            (PyDefDocs|str): docs
        """
        _docs = upy_docs.PyDefDocs(
            self.to_docstring(), def_=self, def_name=self.name)
        _result = None
        if mode == 'Object':
            _result = _docs
        elif mode == 'Header':
            if _docs:
                _result = _docs.header
        elif mode == 'Title':
            if _docs:
                _result = _docs.title
        else:
            raise ValueError(mode)
        return _result


def _ast_attr_to_val(attr, catch=False):
    """Obtain a value from an ast attribute.

    This occurs when ast encounters an attibute as a default value.

        eg. def _test(arg=lucididy.Template.ANCHOR_END)

    Args:
        attr (Attribute): ast attribute to read
        catch (bool): no error if fail to find attribute value - this
            can happen if this module cannot be imported (eg. for a
            maya module outside maya)

    Returns:
        (any): value of attribute
    """
    _LOGGER.info(
        'READ ATTR %s attr=%s val=%s', attr, attr.attr, attr.value)
    _attr = attr
    _path = []
    _LOGGER.info(' - ATTR %s', _attr)
    while hasattr(_attr, 'value'):
        check_heart()
        _path.insert(0, _attr.attr)
        _LOGGER.info(' - PATH %s %s', _path, _attr)
        _attr = _attr.value
    _attr_name = '.'.join(_path)
    _mod_name = _attr.id
    try:
        _mod = importlib.import_module(_mod_name)
    except ModuleNotFoundError as _exc:
        if catch:
            return None
        raise _exc
    _parent = _mod
    while len(_path) > 1:
        check_heart()
        _parent = getattr(_parent, _path.pop(0))
        _LOGGER.info(' - PARENT %s', _parent)
    try:
        return getattr(_parent, single(_path))
    except AttributeError as _exc:
        _LOGGER.info(' - FAILED TO READ ATTR VAL %s', attr)
        if catch:
            return None
        raise _exc


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
