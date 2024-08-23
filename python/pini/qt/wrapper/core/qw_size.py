"""Tools for adding functionality to QSize object."""

import logging

from ...q_mgr import QtCore

_LOGGER = logging.getLogger(__name__)


class CSize(QtCore.QSize):
    """Wrapper for QSize object."""

    def aspect(self):
        """Obtain aspect of this size.

        Returns:
            (float): width/height
        """
        return self.width() / self.height()

    def to_tuple(self):
        """Obtain this vector's values.

        Returns:
            (tuple): width/height values
        """
        return self.width(), self.height()

    def __mul__(self, other):

        if isinstance(other, (float, int)):
            return CSize(self.width()*other, self.height()*other)
        if isinstance(other, (QtCore.QSize, QtCore.QSize)):
            return CSize(
                self.width()*other.width(), self.height()*other.height())

        raise NotImplementedError(other)
