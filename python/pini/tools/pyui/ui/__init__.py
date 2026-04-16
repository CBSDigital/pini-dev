"""Tools for managing pyui interfaces."""

from pini import dcc

from .pu_build import build

if dcc.NAME == 'maya':
    from .pu_maya import PUMayaUi
