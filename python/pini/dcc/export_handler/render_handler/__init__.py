"""Tools for managing render handlers."""

from pini import dcc

from .rh_base import CRenderHandler

if dcc.NAME == 'maya':
    from .rh_maya import CMayaRenderHandler, CMayaLocalRender, CMayaFarmRender
