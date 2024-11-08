"""Tools for adding functionality to QRect object."""

import logging

from ...q_mgr import QtCore

_LOGGER = logging.getLogger(__name__)


class CRect(QtCore.QRect):
    """Wrapper for QRect object."""

    def aspect(self):
        """Obtain aspect of this rect.

        Returns:
            (float): width/height
        """
        return self.width() / self.height()
