"""Tools for managing installing tools to nuke."""

import logging

import nuke

from nuke_pini.tools import autowrite

from .. import i_installer, i_tool

_LOGGER = logging.getLogger(__name__)


class PINukeMenuInstaller(i_installer.PIInstaller):
    """Installer to set up pini tools menu in nuke."""

    def _gather_dcc_items(self):
        """Gather nuke-specific items.

        Returns:
            (PITool list): nuke tools
        """
        _autowrite = i_tool.PITool(
            name='Autowrite', icon=autowrite.ICON,
            command='\n'.join([
                'from nuke_pini.tools import autowrite',
                'autowrite.build()']))
        return [_autowrite]

    def run(self, *args, **kwargs):
        """Execute this installer."""
        _LOGGER.info('AUTOWRITE %s', autowrite)

        # Add autowrite
        autowrite.install_callbacks()
        _toolbar = nuke.toolbar("Nodes")
        _toolbar.addCommand(
            "Pini/Autowrite", autowrite.build, icon=autowrite.ICON)

        super().run(*args, **kwargs)


INSTALLER = PINukeMenuInstaller()
