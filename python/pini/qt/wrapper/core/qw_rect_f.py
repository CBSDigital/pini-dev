"""Tools for adding functionality to QRectF object."""

import logging

from ...q_mgr import QtCore

_LOGGER = logging.getLogger(__name__)


class CRectF(QtCore.QRectF):
    """Wrapper for QRectF object."""

    def aspect(self):
        """Obtain aspect of this rect.

        Returns:
            (float): width/height
        """
        return self.width() / self.height()
