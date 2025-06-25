"""Tools for managing export handlers.

These are used to generate outputs (eg. publishes/renders) and can
be embedded in PiniHelper.
"""

from pini import dcc, pipe

from .eh_utils import build_metadata
from .eh_base import CExportHandler
from .eh_ui import to_settings_key

from .eh_blast import blast
from .eh_cache import abc_cache, fbx_cache
from .eh_publish import CBasicPublish, publish, model_publish, lookdev_publish
from .eh_render import CRenderHandler, local_render, farm_render

if pipe.SHOTGRID_AVAILABLE:
    from .eh_submit import submit, CBasicSubmitter

if dcc.NAME == 'maya':
    from .eh_publish import (
        CMayaBasicPublish, CMayaLookdevPublish, CMayaModelPublish,
        PubRefsMode, get_pub_refs_mode, set_pub_refs_mode)
    from .eh_render import (
        CMayaLocalRender, CMayaRenderHandler, CMayaFarmRender)
    from .eh_blast import CMayaPlayblast
    from .eh_cache import (
        CMayaAbcCache, CMayaFbxCache, CMayaCrvsCache, CMayaCache)

elif dcc.NAME == 'hou':
    from .eh_blast import CHouFlipbook

elif dcc.NAME == 'substance':
    from .eh_publish import CSubstanceTexturePublish
