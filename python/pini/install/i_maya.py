"""Tools for managing installation to maya."""

import logging
import os

from maya import cmds

from pini import icons
from pini.tools import helper
from pini.utils import wrap_fn

from maya_pini import ui

from . import i_installer

_LOGGER = logging.getLogger(__name__)


class PIMayaMenuInstaller(i_installer.PIInstaller):
    """Installer for building the pini menu in maya."""

    prefix = 'PM'


class PIMayaShelfInstaller(i_installer.PIInstaller):
    """Installer for building the pini shelf in maya."""

    allows_context = True
    prefix = 'PS'
    shelf = None

    def _gather_reload_tools(self, items):
        """Gather reload tools.

        Args:
            items (list): items list to append to

        Returns:
            (list): updated items list
        """

        # Build reload button
        _refresh, _items = super()._gather_reload_tools(items)
        _refresh.add_divider('MayaRefresh1')

        # Add reset windows
        _cmd = '\n'.join([
            "from maya import cmds",
            "for _win in cmds.lsUI(windows=True):",
            "    cmds.window(_win, edit=True, topLeftCorner=(0, 0))"])
        _reset_windows = i_installer.PITool(
            name='ResetWindows',
            command=_cmd,
            icon=icons.find('Sponge'), label='Reset maya windows')
        _refresh.add_context(_reset_windows)

        # Add redraw viewport
        _cmd = '\n'.join([
            'from maya import cmds',
            'cmds.currentTime(cmds.currentTime(query=True))'])
        _redraw_viewport = i_installer.PITool(
            name='RedrawViewport',
            command=_cmd,
            icon=icons.find('Sponge'), label='Redraw viewport')
        _refresh.add_context(_redraw_viewport)

        return _refresh, _items

    def _build_tool(self, tool, parent=None):
        """Build shelf button tool.

        Args:
            tool (PITool): tool to add
            parent (str): parent shelf
        """
        _name = tool.to_uid(self.prefix)
        _LOGGER.debug('BUILD TOOL %s parent=%s name=%s', tool, parent, _name)
        ui.add_shelf_button(
            name=_name, command=tool.command,
            image=tool.icon,
            parent=self.shelf, annotation=tool.label)
        _LOGGER.debug(
            ' - ADDING CONTEXTS %d %s', len(tool.context_items),
            tool.context_items)
        for _item in tool.context_items:
            self._build_context_item(_item, parent=None)

    def _build_context_item(self, item, parent):
        """Build shelf right-click menu item.

        Args:
            item (PITool): tool to add
            parent (str): parent shelf button
        """
        _LOGGER.debug('BUILD CONTEXT ITEM %s %s', item, parent)
        if isinstance(item, i_installer.PITool):
            ui.add_menu_item(
                label=item.label, parent=parent,
                image=item.icon, command=item.command)
        elif isinstance(item, i_installer.PIDivider):
            cmds.menuItem(divider=True)
        else:
            raise ValueError(item)

    def _build_divider(self, divider, parent=None):
        """Build shelf divider.

        Args:
            divider (PIDivider): divider to build
            parent (str): parent shelf
        """
        _LOGGER.debug('ADD SHELF SEPARATOR %s', divider)
        ui.add_shelf_separator(
            parent=self.shelf, name=self.shelf+'_'+divider.name)

    def run(self, parent=None, launch_helper=True, flush=True):  # pylint: disable=unused-argument
        """Execute this installer.

        Args:
            parent (str): parent shelf name
            launch_helper (bool): not applicable
            flush (bool): flush shelf on run
        """
        _LOGGER.debug('RUN PIMayaShelfInstaller %s', self)
        _shelf_name = parent or os.environ.get('PINI_SHELF', self.name)

        _LOGGER.debug(' - SHELF NAME %s', _shelf_name)
        self.shelf = ui.obtain_shelf(_shelf_name)
        if flush:
            ui.flush_shelf(self.shelf)
        super().run(parent=parent)


class PIMayaInstaller(i_installer.PIInstaller):
    """Combined shelf/menu installer for pini."""

    def __init__(self, menu_installer=None, shelf_installer=None):
        """Constructor.

        Args:
            menu_installer (PIInstaller): menu installer
            shelf_installer (PIInstaller): shelf installer
        """
        super().__init__()

        self.menu_installer = menu_installer or PIMayaMenuInstaller()
        self.shelf_installer = shelf_installer or PIMayaShelfInstaller()

        assert self.menu_installer.prefix != self.shelf_installer.prefix

    def run(self, parent=None, launch_helper=True, deferred=True):
        """Execute combined installer.

        Args:
            parent (str): parent shelf/menu name
            launch_helper (bool): launch pini helper on startup
            deferred (bool): run deferred (required for userSetup.py)
        """
        _func = wrap_fn(
            self._exec_run, parent=parent, launch_helper=launch_helper)
        if deferred:
            cmds.evalDeferred(_func, lowestPriority=True)
        else:
            _func()

    def _exec_run(self, parent=None, launch_helper=True):
        """Execute running this installation.

        Args:
            parent (str): parent shelf/menu name
            launch_helper (bool): launch pini helper on startup
        """
        _LOGGER.info('RUN %s helper=%d', self, launch_helper)
        self.menu_installer.run(parent=parent)
        self.shelf_installer.run(parent=parent)
        if launch_helper:
            _LOGGER.info(' - LAUNCHING HELPER %s', helper)
            helper.obt_helper()


INSTALLER = PIMayaInstaller()
