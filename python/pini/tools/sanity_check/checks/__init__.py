"""Sanity checks."""

from pini import dcc

from .scc_generic import CheckRefsLatest, CheckAbcFpsMatchesScene

if dcc.NAME == 'maya':
    from .scc_maya_asset import CheckAssetHierarchy
    from .scc_maya_render import CheckRenderGlobals
