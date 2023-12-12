"""Tools for managing pini installation.

This is run each time a dcc launches to set up pini tools.
"""

from pini import dcc

from .i_tools import setup
from .i_installer import CIInstaller, CITool, CIDivider

INSTALLER = None

if dcc.NAME == 'hou':
    from .i_hou import CIHouShelfInstaller
    INSTALLER = CIHouShelfInstaller()

elif dcc.NAME == 'maya':
    from .i_maya import (
        CIMayaCombinedInstaller, CIMayaShelfInstaller, CIMayaMenuInstaller)
    INSTALLER = CIMayaCombinedInstaller()

elif dcc.NAME == 'nuke':
    from .i_nuke import CINukeMenuInstaller
    INSTALLER = CINukeMenuInstaller()
