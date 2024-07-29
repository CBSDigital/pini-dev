"""Tools for adding functionality to QSizeF object."""

import logging

from ...q_mgr import QtCore

_LOGGER = logging.getLogger(__name__)


class CSizeF(QtCore.QSizeF):
    """Wrapper for QSizeF object."""

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
            return CSizeF(self.width()*other, self.height()*other)
        if isinstance(other, (QtCore.QSize, QtCore.QSizeF)):
            return CSizeF(
                self.width()*other.width(), self.height()*other.height())

        raise NotImplementedError(other)
