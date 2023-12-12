"""Tools for managing the QTreeWidget wrapper."""

from pini.utils import single

from ...q_mgr import QtWidgets, Qt
from ...q_utils import get_application
from .qw_base_widget import CBaseWidget


class CTreeWidget(QtWidgets.QTreeWidget, CBaseWidget):
    """Wrapper for QTreeWidget."""

    def __init__(self, *args, **kwargs):
        """Constructor."""
        super(CTreeWidget, self).__init__(*args, **kwargs)
        self.itemCollapsed.connect(self._collapse_callback)
        self.itemExpanded.connect(self._expand_callback)

    def all_data(self, recursive=True):
        """Retrieve data from all items in tree.

        Args:
            recursive (bool): search children of children

        Returns:
            (any list): all data
        """
        return [
            _item.get_data() for _item in self.all_items(recursive=recursive)]

    def all_items(self, recursive=True):
        """Retrieve all items in the tree.

        Args:
            recursive (bool): search children of children

        Returns:
            (QTreeWidgetItem list): items
        """
        _items = []
        for _idx in range(self.topLevelItemCount()):
            _root = self.topLevelItem(_idx)
            _items += [_root]
            if recursive:
                _items += _root.find_children()
        return _items

    def selected_data(self):
        """Read data from the currently selected item.

        Returns:
            (any): selected data
        """
        _sel = single(self.selectedItems(), catch=True)
        if not _sel:
            return None
        return _sel.data(0, Qt.UserRole)

    def _collapse_callback(self, item):
        """Triggered by item collapse.

        Allows shift-click to propagate to child items.

        Args:
            item (QTreeListItem): item which was collapsed
        """
        _mods = get_application().keyboardModifiers()
        if _mods == Qt.ShiftModifier:
            for _child in item.find_children():
                _child.setExpanded(False)

    def _expand_callback(self, item):
        """Triggered by item expand.

        Allows shift-click to propagate to child items.

        Args:
            item (QTreeListItem): item which was expanded
        """
        _mods = get_application().keyboardModifiers()
        if _mods == Qt.ShiftModifier:
            for _child in item.find_children():
                _child.setExpanded(True)
