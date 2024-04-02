"""Tools for managing export handlers.

These are used to generate outputs (eg. publishes/renders) and can
be embedded in PiniHelper.
"""

from pini import dcc

from .eh_base import CExportHandler
from .eh_utils import obtain_metadata
from .render import CRenderHandler
from .publish import CBasicPublish

if dcc.NAME == 'maya':
    from .publish import (
        CMayaBasicPublish, CMayaLookdevPublish, CMayaModelPublish,
        ReferencesMode, get_publish_references_mode)
    from .render import (
        CMayaLocalRender, CMayaRenderHandler, CMayaFarmRender)
    from .blast import CMayaPlayblast

elif dcc.NAME == 'hou':
    from .blast import CHouFlipbook
