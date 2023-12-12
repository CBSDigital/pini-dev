"""Tools for managing installing tools to nuke."""

import logging

from . import i_installer

_LOGGER = logging.getLogger(__name__)


class CINukeMenuInstaller(i_installer.CIInstaller):
    """Installer to set up pini tools menu in nuke."""
