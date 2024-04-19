"""Tools for managing pini installation.

This is run each time a dcc launches to set up pini tools.
"""

from pini import dcc

from .i_utils import setup
from .i_installer import PIInstaller, PITool, PIDivider
from .i_tools import (
    REFRESH_TOOL, PINI_HELPER_TOOL, LOAD_RECENT_TOOL, VERSION_UP_TOOL)

INSTALLER = None

if dcc.NAME == 'hou':
    from .i_hou import (
        PIHouShelfInstaller, PIHouMenuInstaller, MENU_INSTALLER,
        SHELF_INSTALLER)

elif dcc.NAME == 'maya':
    from .i_maya import (
        PIMayaInstaller, PIMayaShelfInstaller, PIMayaMenuInstaller,
        INSTALLER)

elif dcc.NAME == 'nuke':
    from .i_nuke import PINukeMenuInstaller, INSTALLER
