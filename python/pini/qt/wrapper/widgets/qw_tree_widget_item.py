"""Tools for managing the QTreeWidgetItem wrapper."""

from pini.utils import basic_repr

from ...q_mgr import QtWidgets, Qt, QtGui
from ...q_utils import to_col


class CTreeWidgetItem(QtWidgets.QTreeWidgetItem):
    """Wrapper for QTreeWidgetItem."""

    def __init__(self, text=None, data=None, col=None):
        """Constructor.

        Args:
            text (str): item text
            data (any): item data
            col (QColor): item colour
        """
        super().__init__()
        if text:
            self.setText(0, text)
        if data:
            self.setData(0, Qt.UserRole, data)
        if col:
            _col = to_col(col)
            _brush = QtGui.QBrush(_col)
            self.setForeground(0, _brush)

    def find_children(self):
        """Find children of this widget.

        Returns:
            (QTreeListItem list): children
        """
        _children = []
        for _idx in range(self.childCount()):
            _child = self.child(_idx)
            _children += [_child] + _child.find_children()
        return _children

    def get_data(self):
        """Get this item's data.

        Returns:
            (any): item data
        """
        return self.data(0, Qt.UserRole)

    def __repr__(self):
        return basic_repr(self, self.text(0))
