"""Tools for adding functionality to QListWidgetItem."""

from pini.utils import EMPTY

from ...q_utils import to_col
from ...q_mgr import QtWidgets, Qt, QtGui


class CListWidgetItem(QtWidgets.QListWidgetItem):
    """Wrapper for QListWidgetItem."""

    def __init__(
            self, text='', data=EMPTY, icon=None, icon_scale=None, col=None):
        """Constructor.

        Args:
            text (str): item text
            data (any): item data
            icon (str): path to item icon
            icon_scale (float): apply icon scaling
            col (str|tuple|QColor): item text colour
        """
        super().__init__(text)
        if data is not EMPTY:
            self.setData(Qt.UserRole, data)
        if icon:
            self.set_icon(icon, icon_scale=icon_scale)
        if col:
            self.set_col(col)

    def data(self, role=Qt.UserRole):  # pylint: disable=useless-super-delegation
        """Obtain data stored in this item.

        Args:
            role (int): data role

        Returns:
            (any): stored data
        """
        return super().data(role)

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

    def set_icon(self, image, icon_scale=None):
        """Set item icon.

        Args:
            image (str): path to image
            icon_scale (float): apply icon scaling
        """
        _image = image
        if icon_scale:
            from pini import qt
            _image = qt.CPixmap(100, 100)
            _image.fill('Transparent')
            _image.draw_overlay(
                image, _image.center(), size=100 * icon_scale, anchor='C')
        _icon = QtGui.QIcon(_image)
        self.setIcon(_icon)

    def __repr__(self):
        _name = type(self).__name__.strip("_")
        return f'<{_name}>'
