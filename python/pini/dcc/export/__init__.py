"""Tools for managing export handlers.

These are used to generate outputs (eg. publishes/renders) and can
be embedded in PiniHelper.
"""

from pini import dcc

from .eh_utils import build_metadata
from .eh_base import CExportHandler

from .eh_render import CRenderHandler
from .eh_publish import CBasicPublish
from .eh_cache import cache

if dcc.NAME == 'maya':
    from .eh_publish import (
        CMayaBasicPublish, CMayaLookdevPublish, CMayaModelPublish,
        PubRefsMode, get_pub_refs_mode, set_pub_refs_mode, publish)
    from .eh_render import (
        CMayaLocalRender, CMayaRenderHandler, CMayaFarmRender)
    from .eh_blast import CMayaPlayblast
    from .eh_cache import CMayaCache

elif dcc.NAME == 'hou':
    from .eh_blast import CHouFlipbook
