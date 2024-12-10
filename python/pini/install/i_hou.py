"""Tools for managing installing tools to houdini."""

import logging
import os

import hou

from pini import qt, icons, dcc
from pini.tools import release
from pini.utils import cache_result, TMP, File, HOME

from . import i_installer, i_tool

_LOGGER = logging.getLogger(__name__)


class _PIHouBaseInstaller(i_installer.PIInstaller):
    """Base class for any houdini installer.

    Adds houdini-specific tools.
    """

    parent = 'Pini'

    def _build_context_item(self, item, parent):
        """Build a context (right-clikc) item.

        Args:
            item (PITool/PIDivider): context item
            parent (any): item parent
        """
        raise NotImplementedError

    def _gather_dcc_items(self):
        """Gather houdini-specific tools."""
        _fmt = os.environ.get('PINI_VIDEO_FORMAT', 'mp4')
        _flipbook = i_installer.PITool(
            name='FlipbookMp4', command='\n'.join([
                'from hou_pini import h_pipe',
                'h_pipe.flipbook()']),
            icon=icons.find('collision'), label=f'Flipbook {_fmt.upper()}')
        return [_flipbook]


class PIHouShelfInstaller(_PIHouBaseInstaller):
    """Installs items to a houdini shelf."""

    @property
    def shelf_file(self):
        """Obtain path to shelf file in the user home directory.

        Returns:
            (str): path to shelf file
        """
        _prefs = os.environ['HOUDINI_USER_PREF_DIR']
        return f'{_prefs}/toolbar/{self.name}.shelf'

    def _build_context_item(self, item, parent):
        """Build a context (right-click) item.

        Args:
            item (PITool/PIDivider): context item
            parent (any): item parent
        """
        raise NotImplementedError

    def _build_tool(self, tool, parent=None):
        """Build a shelf item for the given tool.

        Args:
            tool (PITool): tool to add
            parent (any): not applicable for this installer

        Returns:
            (Tool): houdini tool object
        """
        _LOGGER.debug('BUILD TOOL %s', tool)
        del parent

        _uid = tool.to_uid(prefix=self.prefix)
        if _uid in hou.shelves.tools():
            hou.shelves.tools()[_uid].destroy()
        if not isinstance(tool.command, str):
            _LOGGER.debug(' - FAILED TO ADD TOOL %s', _uid)
            return None

        _LOGGER.debug('    - ADD TOOL %s icon=%s', _uid, tool.icon)

        assert '\b' not in tool.command
        assert isinstance(tool.icon, str)
        assert os.path.exists(tool.icon)

        _tool = hou.shelves.newTool(
            file_path=self.shelf_file, name=_uid,
            label=tool.label,
            script=tool.command,
            icon=_fix_icon_gamma(tool.icon))
        _LOGGER.debug('    - NEW TOOL %s', _tool)

        return _tool

    def _build_divider(self, divider, parent=None):
        """Build a shelf divider item.

        Args:
            divider (PIDivider): divider to add
            parent (any): not applicable for this installer

        Returns:
            (Tool): houdini tool object
        """
        _tool = i_installer.PITool(
            name=divider.name, label=' ', command='',
            icon=_obtain_shelf_divider_icon())
        return self._build_tool(_tool)

    def run(self, parent=None, launch_helper=True):  # pylint: disable=unused-argument
        """Execute this install.

        Args:
            parent (any): not applicable for this installer
            launch_helper (bool): launch pini helper on startup
        """
        _LOGGER.debug('INSTALL SHELF %s', self)
        _LOGGER.debug(' - FILE %s', self.shelf_file)

        # Check for disabled + batch mode
        if os.environ.get('PINI_INSTALL_UI_DISABLE'):
            _LOGGER.info(" - SHELF SETUP DISABLED VIA $PINI_INSTALL_UI_DISABLE")
            return
        if dcc.batch_mode():
            _LOGGER.info(" - SHELF SETUP DISABLED IN BATCH MODE")
            return

        # Make sure this shelf exists
        if self.name not in hou.shelves.shelves():
            hou.shelves.newShelf(
                file_path=self.shelf_file, name=self.name, label=self.label)
        _shelf = hou.shelves.shelves()[self.name]

        _tools = super().run()

        _LOGGER.debug(' - TOOLS %d %s', len(_tools), _tools)
        _shelf.setTools(_tools)


SHELF_INSTALLER = PIHouShelfInstaller()


class PIHouMenuInstaller(_PIHouBaseInstaller):
    """Used for checking houdini menu installs.

    As there's no python api for houdini menus, this can't be automated but
    this installer be used to check the menu xml file.
    """

    xml_file = release.PINI.to_file('startup/hou/MainMenuCommon.xml')

    def _build_context_item(self, item, parent):
        """Build a context (right-click) item.

        Args:
            item (PITool/PIDivider): context item
            parent (any): item parent
        """
        raise NotImplementedError

    def _gather_reload_tools(self, items):
        """Gather reload tools.

        For shelves, the reload button is added at the front, but for menus
        the button is added at the end.

        Args:
            items (list): items list to append to

        Returns:
            (list): updated items list
        """
        _tool, _items = super()._gather_reload_tools(items)

        _install_shelf = i_tool.PITool(
            name='InstallShelf',
            label='Install Pini Shelf',
            command='\n'.join([
                'from pini import install',
                'install.SHELF_INSTALLER.run()']))
        _items.insert(-1, _install_shelf)

        return _tool, _items

    def to_xml(self):
        """Build xml for this installation.

        Returns:
            (str): menu xml
        """
        _header = '\n'.join([
            '<?xml version="1.0" encoding="UTF-8"?>',
            '<mainMenu>',
            '  <menuBar>',
            '    <subMenu id="{id}">',
            '      <label>{label}</label>',
        ]).format(label=self.label, id=self.to_uid())

        _footer = '\n'.join([
            '    </subMenu>',
            '  </menuBar>',
            '</mainMenu>',
        ])

        _xmls = self.run()
        _xmls = [
            _header,
            ''] + _xmls + [
            '', _footer]
        _xml = '\n'.join(_xmls)

        return _xml

    def check_xml(self, xml=None, edit=False, force=False):
        """Check the given xml file contains the desired tools.

        Args:
            xml (File): path to xml file
            edit (bool): edit the xml file
            force (bool): update xml without confirmation
        """
        _new_xml = self.to_xml()

        # Check xml up to date
        _xml_file = File(xml or self.xml_file)
        if not _xml_file.exists():
            if not force:
                qt.ok_cancel('Write shelf xml?\n\n'+_xml_file.path)
            _xml_file.write(_new_xml)
        else:  # Compare existing xml
            _cur_xml = _xml_file.read()
            if _cur_xml == _new_xml:
                _LOGGER.info('XML is good %s', xml)
            else:
                _xml_file.write(_new_xml, force=force)

        if edit:
            _xml_file.edit()


MENU_INSTALLER = PIHouMenuInstaller()


def _fix_icon_gamma(icon):
    """Fix gamma in android icons.

    Android icons have embedded gamma 2.2, making them appear in a bad
    colourspace in houdini. If they're run through QPixmap then this
    fixes the issue.

    Args:
        icon (str): path to icon to check

    Returns:
        (str): path to use for icon
    """
    _LOGGER.log(9, 'FIX ICON GAMMA %s', icon)

    if not icons.ANDROID.contains(icon):
        return icon

    _cache_dir = HOME.to_subdir('.pini/icons')

    _root = icons.ANDROID.to_dir(levels=2)
    _LOGGER.log(9, ' - ROOT %s', _root)
    _rel_path = _root.rel_path(icon)
    _tmp_path = _cache_dir.to_file(_rel_path)
    _LOGGER.log(9, ' - TMP %s', _root)
    if not _tmp_path.exists():
        _pix = qt.CPixmap(icon)
        _pix.save_as(_tmp_path)
    return _tmp_path.path


@cache_result
def _obtain_shelf_divider_icon(mode='build'):
    """Build the icon for a divider.

    Args:
        mode (str): how to obtain icon (icons/build)

    Returns:
        (str): path to divider icon
    """
    if mode == 'icons':
        _path = r"C:\Users\hvanderbeek\dev\pini-dev\icons\hou_shelf_spacer.png"
        return _path

    if mode == 'build':
        _pix = qt.CPixmap(60, 100)
        _pix.fill('Transparent')
        _pix.draw_overlay(i_installer.ICON, _pix.center(), size=20, anchor='C')
        _tmp_file = TMP.to_file('pini/shelfSepIcon.png')
        _pix.save_as(_tmp_file, force=True)
        return _tmp_file.path

    raise ValueError(mode)
