"""Tools for managing the sanity check interface and api."""

from pini import dcc

from .core import find_checks, SCCheck, find_check, read_checks
from .ui import launch_ui, UI_FILE, ICON, launch_export_ui

if dcc.NAME == 'maya':
    from .core.sc_utils_maya import read_cache_set, SCMayaCheck

DIALOG = None
