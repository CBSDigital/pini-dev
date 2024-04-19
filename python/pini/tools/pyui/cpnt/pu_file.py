"""Tools for managing the PUFile object.

This is a subclass of a basic PyFile object with added tools for
extracting ui data.
"""

import ast
import logging

from pini.utils import PyFile, PyDef, single

from . import pu_section

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


class PUFile(PyFile):
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
        _child = super(PUFile, self)._map_ast_item_to_child(
            item=item, parent=parent)

        if not _child and _ast_item_is_set_section(item):
            _name = item.value.args[0].s
            _kwargs = {}
            for _kwarg in item.value.keywords:
                _k_name = _kwarg.arg
                _k_val = _kwarg.value.value
                _LOGGER.debug(' - ADD KWARG %s %s %s', _k_name, _k_val, _kwarg)
                _kwargs[_k_name] = _k_val
            _child = pu_section.set_section(_name, **_kwargs)

        return _child

    def find_ui_elem(self, match=None):
        """Find a ui element within in this file.

        Args:
            match (str): match by name

        Returns:
            (PUDef|PUSection): matching element
        """
        _elems = self.find_ui_elems()
        if len(_elems) == 1:
            return single(_elems)
        _match_elems = [_elem for _elem in _elems if match in (_elem.name, )]
        if len(_match_elems) == 1:
            return single(_match_elems)
        raise ValueError(match)

    def find_ui_elems(self):
        """Find elements which are to be build into the ui.

        Returns:
            (PUDef|PUSection list): ui elements
        """
        from pini.tools import pyui
        _LOGGER.debug('FIND UI ELEMS %s', self)

        _mod = self.to_module(reload_=True)
        _LOGGER.debug(' - RELOADED MOD %s', _mod)

        _elems = []
        for _child in self.find_children(recursive=False):

            _LOGGER.debug(' - CHECKING CHILD %s', _child)

            if isinstance(_child, pyui.PUSection):
                _elem = _child
                _LOGGER.debug('   - ADDING SECTION %s', _elem)

            elif isinstance(_child, PyDef):
                if _child.internal:
                    continue
                _func = getattr(_mod, _child.name)
                _LOGGER.debug('   - ADDING DEF %s %s', _child, _func)
                if not isinstance(_func, pyui.PUDef):
                    _elem = pyui.PUDef(_func)
                else:
                    _elem = _func
            else:
                continue

            _elem.py_def = _child
            _elem.pyui_file = self

            _elems.append(_elem)

        return _elems
