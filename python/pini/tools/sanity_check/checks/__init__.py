"""Sanity checks."""

from pini import dcc

if dcc.NAME == 'maya':
    from .scc_maya_asset import CheckAssetHierarchy
    from .scc_maya_render import CheckRenderGlobals
