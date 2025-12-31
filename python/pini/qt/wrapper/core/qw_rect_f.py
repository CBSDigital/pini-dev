"""Tools for adding functionality to QRectF object."""

import logging

from pini.utils import basic_repr

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

    def to_anchor(self, anchor='C'):
        """Obtain anchor point from this rectangle.

        Args:
            anchor (str): anchor position (eg. T/B/L/R)

        Returns:
            (CPointF): anchor point
        """
        from pini import qt
        if anchor == 'T':
            return qt.to_p(self.center().x(), self.top())
        if anchor == 'B':
            return qt.to_p(self.center().x(), self.bottom())
        if anchor == 'C':
            return qt.to_p(self.center())
        raise NotImplementedError(anchor)

    def to_tuple(self):
        """Convert this rect to a tuple.

        Returns:
            (float tuple): values
        """
        _tl = self.topLeft()
        return _tl.x(), _tl.y(), self.width(), self.height()

    def __str__(self):
        _vals = self.left(), self.top(), self.width(), self.height()
        _vals_s = ', '.join(f'{_val:.02f}' for _val in _vals)
        return basic_repr(self, _vals_s)
