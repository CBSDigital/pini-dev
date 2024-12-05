"""Tools for managing CListViewWidgetItem."""

from pini.utils import basic_repr

from ...q_mgr import QtGui, QtWidgets, Qt


class CListViewWidgetItem(QtGui.QStandardItem):
    """Item for a CListView which contains a single widget."""

    def __init__(self, list_view, widget=None, height=25, data=None):
        """Constructor.

        Args:
            list_view (CListView): parent list view widget
            widget (QWidget): override contained widget
            height (int): default item height
            data (any): item data to store
        """
        from pini import qt

        self._height = height
        self.widget = widget or QtWidgets.QWidget()
        self.list_view = list_view

        super().__init__()
        if data:
            self.setData(data, Qt.UserRole)
        _size = qt.to_size(self.list_view.get_draw_width(), height)
        self.setSizeHint(_size)

        self.build_ui()
        self.redraw()

    @property
    def height(self):
        """Obtain height for this list view item.

        This is implemented as a property to allow it to be
        calculated dynamically.

        Returns:
            (int): height in pixels
        """
        return self._height

    def build_ui(self):
        """Build ui elements - to be implemented in subclass."""

    def data(self, role=Qt.UserRole):  # pylint: disable=useless-parent-delegation
        """Obtain data embedded in this element.

        Args:
            role (int): override role

        Returns:
            (any): embedded data
        """
        return super().data(role)

    def get_data(self):
        """Obtain any data stored with this item.

        Returns:
            (any): item data
        """
        return self.data(Qt.UserRole)

    def redraw(self, size=None):
        """Redraw this item.

        This passes any width updates in the parent widget through
        to this item's widget via its size hint.

        Args:
            size (QSize): override widget size
        """
        from pini import qt
        _size = size or qt.to_size(self.list_view.width(), self.height)
        self.setSizeHint(_size)

    def set_height(self, height):
        """Set fixed height for this item.

        Args:
            height (int): height to apply
        """
        self._height = height

    def __repr__(self):
        return basic_repr(self, label=None)
