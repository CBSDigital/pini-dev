"""Tools for managing pini installation.

This is run each time a dcc launches to set up pini tools.
"""

from pini import dcc

from .i_utils import setup
from .i_installer import PIInstaller, PITool, PIDivider
from .i_tools import (
    RELOAD_TOOL, PINI_HELPER_TOOL, LOAD_RECENT_TOOL, VERSION_UP_TOOL)

INSTALLER = None

if dcc.NAME == 'hou':
    from .dcc.i_hou import (
        PIHouShelfInstaller, PIHouMenuInstaller, MENU_INSTALLER,
        SHELF_INSTALLER)
elif dcc.NAME == 'maya':
    from .dcc.i_maya import (
        PIMayaInstaller, PIMayaShelfInstaller, PIMayaMenuInstaller,
        INSTALLER)
elif dcc.NAME == 'nuke':
    from .dcc.i_nuke import PINukeMenuInstaller, INSTALLER
elif dcc.NAME == 'substance':
    from .dcc.i_substance import PISubstanceInstaller, INSTALLER
