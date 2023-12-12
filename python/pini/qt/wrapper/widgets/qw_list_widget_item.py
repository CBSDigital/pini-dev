"""Tools for adding functionality to QListWidgetItem."""

from pini.utils import EMPTY

from ...q_utils import to_col
from ...q_mgr import QtWidgets, Qt, QtGui


class CListWidgetItem(QtWidgets.QListWidgetItem):
    """Wrapper for QListWidgetItem."""

    def __init__(self, text='', data=EMPTY, icon=None, col=None):
        """Constructor.

        Args:
            text (str): item text
            data (any): item data
            icon (str): path to item icon
            col (str|tuple|QColor): item text colour
        """
        super(CListWidgetItem, self).__init__(text)
        if data is not EMPTY:
            self.setData(Qt.UserRole, data)
        if icon:
            self.set_icon(icon)
        if col:
            self.set_col(col)

    def data(self, role=Qt.UserRole):  # pylint: disable=useless-super-delegation
        """Obtain data stored in this item.

        Args:
            role (int): data role

        Returns:
            (any): stored data
        """
        return super(CListWidgetItem, self).data(role)

    def set_col(self, col):
        """Set text colour.

        Args:
            col (str|tuple|QColor): colour to apply
        """
        _brush = QtGui.QBrush(to_col(col))
        self.setForeground(_brush)

    def set_data(self, data):
        """Set data for this item.

        Args:
            data (any): data to apply
        """
        self.setData(Qt.UserRole, data)

    def set_icon(self, image):
        """Set item icon.

        Args:
            image (str): path to image
        """
        _icon = QtGui.QIcon(image)
        self.setIcon(_icon)

    def __repr__(self):
        return '<{}>'.format(type(self).__name__.strip("_"))
