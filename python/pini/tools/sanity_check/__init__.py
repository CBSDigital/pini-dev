"""Tools for managing the sanity check interface and api."""

from pini import dcc

from .core import (
    find_checks, SCCheck, find_check, read_checks, SCFail)
from .ui import launch_ui, UI_FILE, ICON, launch_export_ui

if dcc.NAME == 'maya':
    from .utils import (
        read_cache_set_geo, find_top_level_nodes,
        find_cache_set)
    from .core import SCMayaCheck

DIALOG = None
