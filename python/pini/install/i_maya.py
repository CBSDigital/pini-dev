"""Tools for managing installation to maya."""

import logging
import os

from maya import cmds

from pini import icons
from pini.tools import helper
from maya_pini import ui

from . import i_installer

_LOGGER = logging.getLogger(__name__)


class CIMayaMenuInstaller(i_installer.CIInstaller):
    """Installer for building the pini menu in maya."""

    prefix = 'PM'


class CIMayaShelfInstaller(i_installer.CIInstaller):
    """Installer for building the pini shelf in maya."""

    allows_context = True
    prefix = 'PS'
    shelf = None

    def _gather_refresh_tools(self, items):
        """Gather refresh tools.

        Args:
            items (list): items list to append to

        Returns:
            (list): updated items list
        """

        # Build refresh button
        _refresh, _items = super(
            CIMayaShelfInstaller, self)._gather_refresh_tools(items)
        _refresh.add_divider(self.prefix+'_MayaRefresh1')

        # Add reset windows
        _cmd = '\n'.join([
            "from maya import cmds",
            "for _win in cmds.lsUI(windows=True):",
            "    cmds.window(_win, edit=True, topLeftCorner=(0, 0))"])
        _reset_windows = i_installer.CITool(
            name=self.prefix+'_ResetWindows',
            command=_cmd,
            icon=icons.find('Sponge'), label='Reset maya windows')
        _refresh.add_context(_reset_windows)

        # Add redraw viewport
        _cmd = '\n'.join([
            'from maya import cmds',
            'cmds.currentTime(cmds.currentTime(query=True))'])
        _redraw_viewport = i_installer.CITool(
            name=self.prefix+'_RedrawViewport',
            command=_cmd,
            icon=icons.find('Sponge'), label='Redraw viewport')
        _refresh.add_context(_redraw_viewport)

        return _refresh, _items

    def _build_tool(self, tool, parent=None):
        """Build shelf button tool.

        Args:
            tool (CITool): tool to add
            parent (str): parent shelf
        """
        _LOGGER.debug('BUILD TOOL %s %s', tool, parent)
        ui.add_shelf_button(
            name=self.shelf+'_'+tool.name, command=tool.command,
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
            item (CITool): tool to add
            parent (str): parent shelf button
        """
        _LOGGER.debug('BUILD CONTEXT ITEM %s %s', item, parent)
        if isinstance(item, i_installer.CITool):
            ui.add_menu_item(
                label=item.label, parent=parent,
                image=item.icon, command=item.command)
        elif isinstance(item, i_installer.CIDivider):
            cmds.menuItem(divider=True)
        else:
            raise ValueError(item)

    def _build_divider(self, divider, parent=None):
        """Build shelf divider.

        Args:
            divider (CIDivider): divider to build
            parent (str): parent shelf
        """
        _LOGGER.debug('ADD SHELF SEPARATOR %s', divider)
        ui.add_shelf_separator(
            parent=self.shelf, name=self.shelf+'_'+divider.name)

    def run(self, parent=None, launch_helper=True):  # pylint: disable=unused-argument
        """Execute this installer.

        Args:
            parent (str): parent shelf name
            launch_helper (bool): not applicable
        """
        _LOGGER.debug('RUN CIMayaShelfInstaller %s', self)
        _shelf_name = parent or os.environ.get('PINI_SHELF', "Pini")
        _LOGGER.debug(' - SHELF NAME %s', _shelf_name)
        self.shelf = ui.obtain_shelf(_shelf_name)
        super(CIMayaShelfInstaller, self).run(parent=parent)


class CIMayaCombinedInstaller(i_installer.CIInstaller):
    """Combined shelf/menu installer for pini."""

    def __init__(self, menu_installer=None, shelf_installer=None):
        """Constructor.

        Args:
            menu_installer (CIInstaller): menu installer
            shelf_installer (CIInstaller): shelf installer
        """
        super(CIMayaCombinedInstaller, self).__init__()
        self.menu_installer = menu_installer or CIMayaMenuInstaller()
        self.shelf_installer = shelf_installer or CIMayaShelfInstaller()

    def run(self, parent=None, launch_helper=True):
        """Execute combined installer.

        Args:
            parent (str): parent shelf/menu name
            launch_helper (bool): launch pini helper on startup
        """
        _LOGGER.debug('RUN %s', self)
        self.menu_installer.run(parent='Pini')
        self.shelf_installer.run()
        if launch_helper:
            helper.launch()
