"""Tools for managing PiniHelper pipeline tool."""

from pini import dcc

from .ph_utils import (
    output_to_icon, work_to_icon, CSET_ICON, CAM_ICON, LOOKDEV_ICON,
    ABC_ICON, UPDATE_ICON, is_active, output_to_namespace)
from .ph_base import (
    TITLE, UI_FILE, ICON, EMOJI, BasePiniHelper, BKPS_ICON,
    OUTS_ICON)
from .ph_dialog import PiniHelper
from .ph_launch import launch

if dcc.NAME == 'nuke':
    from .dcc.ph_nuke import NukePiniHelper

DIALOG = None
MIXIN = None
