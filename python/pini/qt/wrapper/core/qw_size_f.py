"""Tools for adding functionality to QSizeF object."""

import logging

from ...q_mgr import QtCore

_LOGGER = logging.getLogger(__name__)


class CSizeF(QtCore.QSizeF):
    """Wrapper for QSizeF object."""

    def to_tuple(self):
        """Obtain this vector's values.

        Returns:
            (tuple): width/height values
        """
        return self.width(), self.height()
