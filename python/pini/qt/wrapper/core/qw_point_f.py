"""Tools for adding functionality to QPointF object."""

import logging
import math

from ...q_mgr import QtCore

_LOGGER = logging.getLogger(__name__)


class CPointF(QtCore.QPointF):
    """Wrapper for QPointF object."""

    def bearing(self):
        """Get the bearing of this point vector.

        This is the angle in degrees of the line from the origin to this
        point from the negative x-axis (up/north).

        Returns:
            (float): bearing in degrees
        """
        if not self.x():
            if self.y() > 0:
                return 90.0
            return 270.0
        _ang = math.degrees(math.atan(1.0 * self.y() / self.x()))
        if self.x() < 0:
            _ang += 180
        elif self.y() < 0:
            _ang += 360
        return _ang

    def length(self):
        """Get the distance of this point from the origin.

        Returns:
            (float): distance from origin
        """
        return (self.x()**2 + self.y()**2)**0.5

    def __add__(self, other):
        return CPointF(self.x() + other.x(), self.y() + other.y())

    def __sub__(self, other):
        return CPointF(self.x() - other.x(), self.y() - other.y())

    def __truediv__(self, value):
        return CPointF(self.x() / value, self.y() / value)

    __div__ = __truediv__  # For py2
