"""Tools for managing render handlers."""

from pini import dcc

from .rh_base import CRenderHandler
from .rh_render import local_render

if dcc.NAME == 'maya':
    from .rh_maya import (
        CMayaRenderHandler, CMayaLocalRender, CMayaFarmRender)
