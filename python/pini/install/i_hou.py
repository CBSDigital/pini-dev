"""Tools for managing installing tools to houdini."""

import logging
import os

import hou
import six

from pini import qt, icons, dcc
from pini.utils import cache_result, Dir, TMP_PATH, File, copy_text

from . import i_installer

_LOGGER = logging.getLogger(__name__)


class _CIHouBaseInstaller(i_installer.CIInstaller):
    """Base class for any houdini installer.

    Adds houdini-specific tools.
    """

    def _build_context_item(self, item, parent):
        """Build a context (right-clikc) item.

        Args:
            item (CITool/CIDivider): context item
            parent (any): item parent
        """
        raise NotImplementedError

    def _gather_dcc_items(self):
        """Gather houdini-specific tools."""
        _flipbook = i_installer.CITool(
            name='CI_FlipbookMp4', command='\n'.join([
                'from hou_pini import h_pipe',
                'h_pipe.flipbook()']),
            icon=icons.find('collision'), label='Flipbook MP4')
        return [_flipbook]


class CIHouShelfInstaller(_CIHouBaseInstaller):
    """Installs items to a houdini shelf."""

    @property
    def shelf_file(self):
        """Obtain path to shelf file in the user home directory.

        Returns:
            (str): path to shelf file
        """
        return '{}/toolbar/{}.shelf'.format(
            os.environ['HOUDINI_USER_PREF_DIR'], self.name)

    def _build_context_item(self, item, parent):
        """Build a context (right-click) item.

        Args:
            item (CITool/CIDivider): context item
            parent (any): item parent
        """
        raise NotImplementedError

    def _build_tool(self, tool, parent=None):
        """Build a shelf item for the given tool.

        Args:
            tool (CITool): tool to add
            parent (any): not applicable for this installer

        Returns:
            (Tool): houdini tool object
        """
        del parent

        if tool.name in hou.shelves.tools():
            hou.shelves.tools()[tool.name].destroy()
        if not isinstance(tool.command, six.string_types):
            _LOGGER.debug(' - FAILED TO ADD TOOL %s', tool.name)
            return None

        _LOGGER.debug('    - ADD TOOL %s icon=%s', tool.name, tool.icon)

        assert '\b' not in tool.command
        assert isinstance(tool.icon, six.string_types)
        assert os.path.exists(tool.icon)

        _tool = hou.shelves.newTool(
            file_path=self.shelf_file, name=tool.name,
            label=tool.label,
            script=tool.command,
            icon=tool.icon)
        _LOGGER.debug('    - NEW TOOL %s', _tool)

        return _tool

    def _build_divider(self, divider, parent=None):
        """Build a shelf divider item.

        Args:
            divider (CIDivider): divider to add
            parent (any): not applicable for this installer

        Returns:
            (Tool): houdini tool object
        """
        _tool = i_installer.CITool(
            name=divider.name, label=' ', command='',
            icon=_obtain_shelf_divider_icon())
        return self._build_tool(_tool)

    def run(self, parent='Pini', launch_helper=True):  # pylint: disable=unused-argument
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
                file_path=self.shelf_file, name=self.name, label=self.name)
        _shelf = hou.shelves.shelves()[self.name]

        _tools = super(CIHouShelfInstaller, self).run()

        _LOGGER.debug(' - TOOLS %d %s', len(_tools), _tools)
        _shelf.setTools(_tools)


class CIHouMenuInstaller(_CIHouBaseInstaller):
    """Used for checking houdini menu installs.

    As there's no python api for houdini menus, this can't be automated but
    this installer be used to check the menu xml file.
    """

    def _build_context_item(self, item, parent):
        """Build a context (right-clikc) item.

        Args:
            item (CITool/CIDivider): context item
            parent (any): item parent
        """
        raise NotImplementedError

    def check_xml(self, xml, edit=True):
        """Check the given xml file contains the desired tools.

        Args:
            xml (File): path to xml file
            edit (bool): edit the xml file
        """

        # Build xml + add header/footer
        _header = '<!--Start {} installer xml-->'.format(self.name)
        _footer = '<!--End {} installer xml-->'.format(self.name)
        _xmls = self.run()
        _xmls = [
            '      '+_header,
            ''] + _xmls + [
            '      '+_footer]
        _xml = '\n'.join(_xmls)

        # Compare to file
        _body = File(xml).read()
        if _xml not in _body:

            # Automated xml update
            if _header in _body and _footer in _body:
                raise NotImplementedError

            # Manually fix xml
            print(_xml)
            copy_text(_xml)
            if edit:
                File(xml).edit()
            _LOGGER.info('XML is not good %s', xml)

        else:
            _LOGGER.info('XML is good %s', xml)


@cache_result
def _obtain_shelf_divider_icon():
    """Build the icon for a divider.

    Returns:
        (str): path to divider icon
    """
    _pix = qt.CPixmap(60, 100)
    _pix.fill('Transparent')
    _pix.draw_overlay(i_installer.ICON, _pix.center(), size=20, anchor='C')
    _tmp_file = Dir(TMP_PATH).to_file('pini/shelfSepIcon.png')
    _pix.save_as(_tmp_file, force=True)
    return _tmp_file.path
