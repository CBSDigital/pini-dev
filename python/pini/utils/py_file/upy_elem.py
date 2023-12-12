"""Tools for managing the base class for any py element."""

import ast
import logging

from ..u_filter import passes_filter
from ..u_misc import basic_repr, single

_LOGGER = logging.getLogger(__name__)


class PyElem(object):
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
            _name = '{}.{}'.format(self.parent.name, self._ast.name)
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
        self.py_file.edit(line_n=self._ast.lineno)

    def find_child(self, name, recursive=False):
        """Find a child of this element.

        Args:
            name (str): name to search for
            recursive (bool): include children of children

        Returns:
            (PyElem): matching child element
        """
        return single([
            _child for _child in self.find_children(recursive=recursive)
            if _child.name == name])

    def find_children(self, recursive=False, internal=None, filter_=None):
        """Find children of this element.

        Args:
            recursive (bool): include children of children
            internal (bool): filter by internal state of elements
            filter_ (str): filter by name

        Returns:
            (PyElem list): child elements
        """
        _LOGGER.debug('FIND CHILDREN %s')
        from pini.utils import PyFile

        _children = []

        _parent = None if isinstance(self, PyFile) else self
        _ast = self.to_ast(catch=True)
        if not _ast:
            raise RuntimeError('Failed to read py '+self.py_file.path)
        for _idx, _item in enumerate(_ast.body):

            # Check if ast object is addable
            _LOGGER.debug(' - CHECK ITEM %d %s', _idx, _item)
            _child = self._map_ast_item_to_child(_item, parent=_parent)
            if not _child:
                _LOGGER.debug('   - FAILED TO MAP')
                continue

            if internal is not None and _child.internal != internal:
                _LOGGER.debug('   - INTERNAL FILTERED')
                continue

            if passes_filter(_child.name, filter_):
                _children.append(_child)
                _LOGGER.debug('   - ADDED %s', _child)

            if recursive:
                _children += _child.find_children(internal=internal)

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

    def find_class(self, name):
        """Find a matching child class within this element.

        Args:
            name (str): class name

        Returns:
            (PyClass): matching class
        """
        return single([_class for _class in self.find_classes()
                       if _class.name == name])

    def find_classes(self):
        """Find child classes of this object.

        Returns:
            (PyClass list): child classes
        """
        from pini.utils import PyClass
        return [_elem for _elem in self.find_children()
                if isinstance(_elem, PyClass)]

    def find_def(self, name):
        """Find a child def of this object.

        Args:
            name (str): def name

        Returns:
            (PyDef): child def
        """
        return single([_def for _def in self.find_defs()
                       if _def.name == name])

    def find_defs(self, internal=None, filter_=None):
        """Find child defs of this object.

        Args:
            internal (bool): filter by def internal state
            filter_ (str): filter by name

        Returns:
            (PyDef list): child defs
        """
        from pini.utils import PyDef
        return [_elem for _elem in self.find_children(
                    internal=internal, filter_=filter_)
                if isinstance(_elem, PyDef)]

    def to_ast(self, catch=False):  # pylint: disable=unused-argument
        """Obtain ast object associated with this element.

        Args:
            catch (bool): included for symmetry

        Returns:
            (Module): ast module
        """
        return self._ast

    def __repr__(self):
        return basic_repr(self, self.name)
