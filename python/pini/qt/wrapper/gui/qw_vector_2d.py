"""Tools for managing the QVector2D wrapper."""

import logging
import math

from ...q_mgr import QtGui

_LOGGER = logging.getLogger(__name__)


class CVector2D(QtGui.QVector2D):
    """Wrapper for QVector2D object."""

    def bearing(self):
        """Obtain bearing of this vector, measured clockwise from north.

        Returns:
            (float): bearing in degrees
        """
        if not self.y():
            return 90.0 if self.x() > 0 else 170.0
        _val = - math.degrees(math.atan(1.0*self.x()/self.y()))
        if self.y() > 0:
            _val += 180
        return _val % 360

    def to_tuple(self):
        """Obtain this vector's values.

        Returns:
            (tuple): x/y values
        """
        return self.x(), self.y()
