"""Tools for managing the base class for maya publish handlers."""

import logging

from maya_pini.utils import blast_frame

from .. import ph_basic

_LOGGER = logging.getLogger(__name__)


class CMayaBasePublish(ph_basic.CBasicPublish):
    """Base class for a maya publish."""

    def _apply_snapshot(self, work):
        """Apply take snapshot setting.

        Args:
            work (CPWork): work file
        """
        if self.ui and self.ui.Snapshot.isChecked():
            _LOGGER.info(' - BLAST FRAME %s', work.image)
            blast_frame(work.image, force=True)
