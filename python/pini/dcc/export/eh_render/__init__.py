"""Tools for managing render handlers."""

from pini import dcc

from .rh_base import CRenderHandler
from .rh_tools import local_render, farm_render

if dcc.NAME == 'maya':
    from .rh_maya import (
        CMayaRenderHandler, CMayaLocalRender, CMayaFarmRender)
