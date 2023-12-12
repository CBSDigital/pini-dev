"""Tools for managing the QPoint wrapper."""

import logging

from ...q_mgr import QtCore

_LOGGER = logging.getLogger(__name__)


class CPoint(QtCore.QPoint):
    """Wrapper for QPoint object."""

    def to_tuple(self):
        """Obtain this point's values.

        Returns:
            (tuple): x/y values
        """
        return self.x(), self.y()

    def __add__(self, other):
        from pini import qt
        _class = qt.CPointF if isinstance(other, QtCore.QPointF) else CPoint
        return _class(self.x()+other.x(), self.y()+other.y())

    def __truediv__(self, value):
        from pini import qt
        _class = qt.CPointF if isinstance(value, float) else CPoint
        return _class(self.x()/value, self.y()/value)

    __div__ = __truediv__  # For py2
