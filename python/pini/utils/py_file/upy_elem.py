"""Tools for managing the base class for any py element."""

import ast
import logging
import operator

from ..u_filter import passes_filter, apply_filter
from ..u_misc import basic_repr, single

_LOGGER = logging.getLogger(__name__)


class PyElem:
    """Base class for any python element - eg. file, def, class."""

    parent = None

    def __init__(self, ast_, parent=None, py_file=None):
        """Constructor.

        Args:
            ast_ (Module): ast object
            parent (PyElem): parent element
            py_file (PyFile): parent py file
        """
        self._ast = ast_
        self._py_file = py_file
        self.parent = parent
        self.line_n = self._ast.lineno

    @property
    def clean_name(self):
        """Obtain clean name.

        eg. <PyElem:CUiDialog.a_method> -> a_method

        Returns:
            (str): clean name
        """
        return self._ast.name

    @property
    def defs(self):
        """Obtain defs list.

        Returns:
            (PyDef tuple): defs
        """
        return tuple(self.find_defs())

    @property
    def indent(self):
        """Obtain indent of this element.

        Returns:
            (str): indent (string of spaces)
        """
        return ' ' * self.to_ast().col_offset

    @property
    def internal(self):
        """Whether this element is internal/private.

        Returns:
            (bool): whether internal
        """
        return self.clean_name.startswith('_')

    @property
    def name(self):
        """Obtain name of this element.

        Returns:
            (str): element name
        """
        if self.parent:
            _name = f'{self.parent.name}.{self._ast.name}'
        else:
            _name = self._ast.name
        return _name

    @property
    def py_file(self):
        """Obtain associated python file.

        Returns:
            (PyFile): py file
        """
        return self._py_file

    def edit(self):
        """Edit the element's definition in a text editor."""
        self.py_file.edit(line_n=self.line_n)

    def find_child(self, match, recursive=False):
        """Find a child of this element.

        Args:
            match (str): name to match
            recursive (bool): include children of children

        Returns:
            (PyElem): matching child element
        """
        _children = self.find_children(recursive=recursive)

        _exact_matches = [
            _child for _child in _children if match == _child.name]
        if len(_exact_matches) == 1:
            return single(_exact_matches)

        _clean_matches = [
            _child for _child in _children if match == _child.clean_name]
        if len(_clean_matches) == 1:
            return single(_clean_matches)

        raise ValueError(match)

    def find_children(self, recursive=False, internal=None, filter_=None):
        """Find children of this element.

        Args:
            recursive (bool): include children of children
            internal (bool): filter by internal state of elements
            filter_ (str): filter by name

        Returns:
            (PyElem list): child elements
        """
        _LOGGER.debug('FIND CHILDREN %s', self)
        from pini.utils import PyFile

        _children = []

        _parent = None if isinstance(self, PyFile) else self
        _ast = self.to_ast(catch=True)
        if not _ast:
            raise RuntimeError('Failed to read py ' + self.py_file.path)
        for _idx, _item in enumerate(_ast.body):

            # Check if ast object is addable
            _LOGGER.debug(' - CHECK ITEM %d %s', _idx, _item)
            _child = self._map_ast_item_to_child(_item, parent=_parent)
            _LOGGER.debug('   - CHILD %s', _child)
            if not _child:
                _LOGGER.debug('   - FAILED TO MAP')
                continue

            if passes_filter(_child.name, filter_):
                _children.append(_child)
                _LOGGER.debug('   - ADDED %s', _child)

            if recursive:
                _children += _child.find_children(
                    recursive=recursive, filter_=filter_)

        if internal is not None:
            _children = [
                _child for _child in _children
                if _child.internal != internal]

        return _children

    def _map_ast_item_to_child(self, item, parent):
        """Map an ast item to child object.

        Args:
            item (Module): ast object
            parent (PyElem): parent element

        Returns:
            (list): children
        """
        from pini.utils import PyDef, PyClass

        if isinstance(item, ast.FunctionDef):
            return PyDef(ast_=item, parent=parent, py_file=self.py_file)

        if isinstance(item, ast.ClassDef):
            return PyClass(ast_=item, parent=parent, py_file=self.py_file)

        return None

    def find_class(self, match=None, catch=False):
        """Find a matching child class within this element.

        Args:
            match (str): class name to match
            catch (bool): no error if fail to find class

        Returns:
            (PyClass): matching class
        """
        _classes = self.find_classes()
        if len(_classes) == 1:
            return single(_classes)
        _matches = [_class for _class in _classes if match in (_class.name, )]
        if len(_matches) == 1:
            return single(_matches)

        # Handle fail
        if catch:
            return None
        _match_s = '' if not match else f' "{match}"'
        raise ValueError(f'Failed to find class{_match_s} in {self.name}')

    def find_classes(self):
        """Find child classes of this object.

        Returns:
            (PyClass list): child classes
        """
        from pini.utils import PyClass
        return [_elem for _elem in self.find_children()
                if isinstance(_elem, PyClass)]

    def find_def(self, match=None, internal=None, recursive=False, catch=False):
        """Find a child def of this object.

        Args:
            match (str): def name
            internal (bool): filter by def internal state
            recursive (bool): include children of children
            catch (bool): no error if fail to find def

        Returns:
            (PyDef): child def
        """
        _LOGGER.debug('FIND DEF %s', match)
        _defs = self.find_defs(internal=internal, recursive=recursive)
        _LOGGER.debug(' - FOUND %d DEFS %s', len(_defs), _defs)

        if len(_defs) == 1:
            return single(_defs)

        _matches = [
            _def for _def in _defs
            if match in {_def.name, _def.clean_name}]
        _LOGGER.debug(' - FOUND %d MATCHES %s', len(_matches), _matches)
        if len(_matches) == 1:
            return single(_matches)

        _filter_matches = apply_filter(
            _defs, match, key=operator.attrgetter('name'))
        if len(_filter_matches) == 1:
            return single(_filter_matches)

        if catch:
            return None
        raise ValueError(match)

    def find_defs(self, filter_=None, internal=None, recursive=False):
        """Find child defs of this object.

        Args:
            filter_ (str): filter by name
            internal (bool): filter by def internal state
            recursive (bool): include children of children

        Returns:
            (PyDef list): child defs
        """
        from pini.utils import PyDef
        return [_elem for _elem in self.find_children(
            internal=internal, filter_=filter_, recursive=recursive)
            if isinstance(_elem, PyDef)]

    def to_ast(self, catch=False):  # pylint: disable=unused-argument
        """Obtain ast object associated with this element.

        Args:
            catch (bool): included for symmetry

        Returns:
            (Module): ast module
        """
        return self._ast

    def to_code(self):
        """Obtain this element's code.

        Returns:
            (str): element code
        """
        _lines = self.py_file.read_lines()
        _ast = self.to_ast()
        return '\n'.join(_lines[_ast.lineno - 1:_ast.end_lineno])

    def to_docstring(self):
        """Obtain docstring.

        Returns:
            (str): docs
        """
        return ast.get_docstring(self.to_ast())

    def __repr__(self):
        return basic_repr(self, self.name)
