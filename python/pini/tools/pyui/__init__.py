"""Tools for building an interface based on a python file."""

import sys

from .cpnt import PUFile, set_section, PUSection, PUDef, PUChoiceMgr
from .ui import build
from .pu_install import install
from .pu_tools import find_ui

if not hasattr(sys, 'PYUI_INTERFACES'):
    sys.PYUI_INTERFACES = {}
UIS = sys.PYUI_INTERFACES
