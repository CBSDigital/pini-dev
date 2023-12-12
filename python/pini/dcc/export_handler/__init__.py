"""Tools for managing export handlers.

These are used to generate outputs (eg. publishes/renders) and can
be embedded in PiniHelper.
"""

from pini import dcc

from .eh_base import CExportHandler
from .eh_utils import obtain_metadata
from .render_handler import CRenderHandler
from .publish_handler import CBasicPublish

if dcc.NAME == 'maya':
    from .publish_handler import (
        CMayaBasicPublish, CMayaLookdevPublish, CMayaModelPublish)
    from .render_handler import (
        CMayaLocalRender, CMayaRenderHandler, CMayaFarmRender)
    from .blast_handler import CMayaPlayblast

elif dcc.NAME == 'hou':
    from .blast_handler import CHouFlipbook
