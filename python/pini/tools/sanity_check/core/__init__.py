"""Tools for managing sanity checks."""

from pini import dcc

from .sc_check import SCCheck, SCPipeCheck
from .sc_checks import find_checks, find_check, read_checks
from .sc_fail import SCFail

if dcc.NAME == 'maya':
    from .sc_utils_maya import SCMayaCheck, find_top_level_nodes
