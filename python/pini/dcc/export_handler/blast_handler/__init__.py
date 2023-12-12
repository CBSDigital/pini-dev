"""Tools for managing blast handlers."""

from pini import dcc

if dcc.NAME == 'hou':
    from .bh_hou import CHouFlipbook
if dcc.NAME == 'maya':
    from .bh_maya import CMayaPlayblast
