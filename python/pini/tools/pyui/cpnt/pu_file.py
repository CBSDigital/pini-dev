"""Tools for managing the PUFile object.

This is a subclass of a basic PyFile object with added tools for
extracting ui data.
"""

import ast
import logging

from pini import icons, install
from pini.utils import (
    PyFile, PyDef, single, str_to_seed, abs_path, to_nice, to_pascal)

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

    @property
    def icon(self):
        """Obtain icon for this file's interface.

        Returns:
            (str): path to icon
        """
        _mod = self.to_module()
        if hasattr(_mod, 'ICON'):
            return _mod.ICON
        _path = abs_path(self.path)
        _rand = str_to_seed(_path)
        return _rand.choice(icons.FRUIT)

    @property
    def title(self):
        """Obtain title for this file's interface.

        Returns:
            (str): title
        """
        _mod = self.to_module()
        if hasattr(_mod, 'PYUI_TITLE'):
            return _mod.PYUI_TITLE
        _tokens = _mod.__name__.split('.')
        if _tokens[-1] == '__init__':
            _tokens.pop()
        return to_nice(_tokens[-1]).title()

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
        _child = super()._map_ast_item_to_child(
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

    def to_tool(self, prefix='', title=None, label=None):
        """Build this interface into a pini install tool.

        Args:
            prefix (str): add prefix to object names
            title (str): override tool title (ie. the name of
                any iterface it creates)
            label (str): override tool label (ie. how it will
                appear in a menu)

        Returns:
            (PITool): interface as a tool
        """
        from pini.tools import pyui

        _LOGGER.debug(' - ADD TOOLKIT %s', self.path)
        _LOGGER.debug('   - TITLE %s', self.title)

        _name = prefix + to_pascal(self.title)
        _path = abs_path(self.path)

        _title = title or self.title
        _label = label or _title
        _tool = install.PITool(
            _name, label=_label,
            command='\n'.join([
                'from pini.tools import pyui',
                f'pyui.build("{_path}", title="{_title}")']),
            icon=self.icon)

        # Add standard options
        _copy = install.PITool(
            _name + 'Copy', label='Copy path',
            command='\n'.join([
                'from pini.utils import copy_text',
                f'copy_text("{_path}")']),
            icon=icons.COPY)
        _tool.add_context(_copy)
        _edit = install.PITool(
            _name + 'Edit', label='Edit file',
            command='\n'.join([
                'from pini.utils import File',
                f'File("{_path}").edit()']),
            icon=icons.EDIT)
        _tool.add_context(_edit)

        # Add contents as context options
        _div_count = 0
        for _elem in self.find_ui_elems():
            if isinstance(_elem, pyui.PUDef):
                if not _div_count:
                    _tool.add_divider(_name + str(_div_count))
                    _div_count += 1
                _ctx = install.PITool(
                    name=_name + to_pascal(_elem.label),
                    label=_elem.label, icon=_elem.icon,
                    command=_elem.to_execute_py())
                _tool.add_context(_ctx)
            elif isinstance(_elem, pyui.PUSection):
                _tool.add_divider(_name + str(_div_count), label=_elem.name)
                _div_count += 1
            else:
                raise ValueError(_elem)

        return _tool
