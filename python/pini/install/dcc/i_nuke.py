"""Tools for managing installing tools to nuke."""

import logging

from .. import i_installer

_LOGGER = logging.getLogger(__name__)


class PINukeMenuInstaller(i_installer.PIInstaller):
    """Installer to set up pini tools menu in nuke."""


INSTALLER = PINukeMenuInstaller()
