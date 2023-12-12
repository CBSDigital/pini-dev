"""Tools for managing the PyUiFile object.

This is a subclass of a basic PyFile object with added tools for
extracting ui data.
"""

import ast
import logging

from pini.utils import PyFile, PyDef

from . import pu_section, pu_install

_LOGGER = logging.getLogger(__name__)


def _ast_item_is_set_section(item):
    """Check whether an ast item is pyui.set_section statement.

    Args:
        item (Module): ast object

    Returns:
        (bool): whether set section statement
    """
    return (
        isinstance(item, ast.Expr) and
        hasattr(item.value, 'func') and
        hasattr(item.value.func, 'attr') and
        item.value.func.attr == 'set_section' and
        item.value.func.value.id == 'pyui')


class PyUiFile(PyFile):
    """Represents a python file to be built into a ui."""

    def _map_ast_item_to_child(self, item, parent):
        """Map an ast item to child object.

        In addition to matching functions, this also matches pyui.set_section
        statements so these can be included in the ui.

        Args:
            item (Module): ast object
            parent (PyElem): parent element

        Returns:
            (list): children
        """
        _child = super(PyUiFile, self)._map_ast_item_to_child(
            item=item, parent=parent)

        if not _child and _ast_item_is_set_section(item):
            _name = item.value.args[0].s
            _child = pu_section.set_section(_name)

        return _child

    def find_ui_elems(self):
        """Find elements which are to be build into the ui.

        Returns:
            (list): ui elements
        """
        _mod = self.to_module(reload_=True)
        _elems = []
        for _child in self.find_children(recursive=False):

            _LOGGER.debug(' - CHECKING CHILD %s', _child)

            if isinstance(_child, pu_section.PyUiSection):
                _elem = _child
                _LOGGER.debug('   - ADDING SECTION %s', _elem)

            elif isinstance(_child, PyDef):
                if _child.internal:
                    continue
                _func = getattr(_mod, _child.name)
                _LOGGER.debug('   - ADDING DEF %s %s', _child, _func)
                if not isinstance(_func, pu_install.PyUiFunc):
                    _elem = pu_install.PyUiFunc(_func)
                else:
                    _elem = _func
            else:
                continue

            _elems.append(_elem)

        return _elems
