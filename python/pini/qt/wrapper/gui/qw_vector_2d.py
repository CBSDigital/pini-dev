"""Tools for managing the QVector2D wrapper."""

import logging

from ...q_mgr import QtGui

_LOGGER = logging.getLogger(__name__)


class CVector2D(QtGui.QVector2D):
    """Wrapper for QVector2D object."""

    def to_tuple(self):
        """Obtain this vector's values.

        Returns:
            (tuple): x/y values
        """
        return self.x(), self.y()
