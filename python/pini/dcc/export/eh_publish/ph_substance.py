"""Tools for managing texture publishing from substance."""

# pylint: disable=unused-argument

import logging

from pini import icons

from substance_pini import s_pipe

from . import ph_basic

_LOGGER = logging.getLogger(__name__)


class CSubstanceTexturePublish(ph_basic.CBasicPublish):
    """Manages a substance texture publish."""

    NAME = 'Substance Texture Publish'
    ICON = icons.find('Framed Picture')
    COL = 'Salmon'
    TYPE = 'Publish'

    LABEL = '\n'.join([
        'Saves textures to disk',
    ])

    def export(
            self, notes=None, snapshot=True, version_up=True,
            progress=True, browser=False, force=False):
        """Execute texture publish.

        Args:
            notes (str): publish notes
            snapshot (bool): take snapshot on publish
            version_up (bool): version up on publish
            progress (bool): show publish progress
            browser (bool): open export folder in brower
            force (bool): replace existing without confirmation
        """
        return s_pipe.export_textures(
            work=self.work, browser=browser, force=force,
            progress=self.progress)
