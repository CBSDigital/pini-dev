"""Tools for building an interface based on a python file."""

import sys

from pini import dcc

from .cpnt import PUFile, set_section, PUSection, PUDef, PUChoiceMgr
from .ui import build
from .pu_install import install
from .pu_tools import find_ui

if dcc.NAME == 'maya':
    from .ui import PUMayaUi

if not hasattr(sys, 'PYUI_INTERFACES'):
    sys.PYUI_INTERFACES = {}
UIS = sys.PYUI_INTERFACES
