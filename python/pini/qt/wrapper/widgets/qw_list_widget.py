"""Tools for adding functionality to QListWidget."""

import logging

from pini.utils import single, EMPTY

from .qw_base_widget import CBaseWidget
from .qw_list_widget_item import CListWidgetItem
from ...q_mgr import QtWidgets, Qt
from ... import q_utils

_LOGGER = logging.getLogger(__name__)


class CListWidget(QtWidgets.QListWidget, CBaseWidget):
    """Wrapper for QListWidget."""

    is_empty = False
    empty_marker = None  # Item used to show list is empty
    save_policy = q_utils.SavePolicy.NO_SAVE

    __repr__ = CBaseWidget.__repr__

    def all_data(self):
        """Get all item data.

        Returns:
            (any list): data from each item
        """
        return [_item.data(Qt.UserRole) for _item in self.all_items()]

    def all_items(self):
        """List all items.

        Returns:
            (QListWidgetItem list): list of items
        """
        if self.is_empty:
            return []
        return [self.item(_idx) for _idx in range(self.count())]

    def all_text(self):
        """Get a list of all item text.

        Returns:
            (str list): item texts
        """
        return [_item.text() for _item in self.all_items()]

    def get_val(self):
        """Get selected text.

        Returns:
            (str): selected text
        """
        return self.currentText()

    def select(self, match, replace=False, emit=True, catch=False):
        """Select an item in the list by item/text/data.

        Args:
            match (any): item/text/data to match
            replace (bool): replace current selection
            emit (bool): emit changed signals on selection
            catch (bool): no error if fail to select data
        """

        # Apply multi select
        if isinstance(match, (list, tuple)):
            self.clearSelection()
            for _item in match:
                self.select(_item, replace=False, catch=True)
            return

        # Apply single selection
        for _idx, _item in enumerate(self.all_items()):
            if match in (
                    _item, _item.data(Qt.UserRole), _item.text()):
                self.select_row(_idx, emit=emit, replace=replace)
                return
        if not catch:
            raise ValueError(f'Failed to select {match}')

    def select_data(self, data, emit=True, catch=False):
        """Select item by its data.

        Args:
            data (any): data to select
            emit (bool): emit changed signals on selection
            catch (bool): no error if fail to select data
        """
        for _idx, _item in enumerate(self.all_items()):
            if _item.data(Qt.UserRole) == data:
                self.select_row(_idx, emit=emit)
                return
        if not catch:
            raise ValueError(f'Failed to select {data}')

    def select_item(self, item, emit=True, catch=False):
        """Select the given item.

        Args:
            item (QListWidgetItem): item to select
            emit (bool): emit signal on selection
            catch (bool): no error if failed to find item
        """
        for _idx, _item in enumerate(self.all_items()):
            if _item is item:
                self.select_row(_idx, emit=emit)
                return
        if not catch:
            raise ValueError(f'Failed to select {item}')

    def select_row(self, idx, replace=True, emit=True):
        """Set current row.

        Args:
            idx (int): row index to select
            replace (bool): replace current selection
            emit (bool): emit changed signals on selection
        """
        if not emit:
            self.blockSignals(True)
        if replace:
            self.clearSelection()
        _item = self.item(idx)
        self.setCurrentItem(_item)
        if not emit:
            self.blockSignals(False)

    def select_rows(self, idxs, emit=True):
        """Select the given row indices.

        Args:
            idxs (int list): rows to select
            emit (bool): emit item selection changed
        """
        _blocked = self.signalsBlocked()
        self.blockSignals(True)
        for _idx, _item in enumerate(self.all_items()):
            _item.setSelected(_idx in idxs)
        if emit:
            self.itemSelectionChanged.emit()
        self.blockSignals(_blocked)

    def select_text(self, text, catch=True):
        """Select item by text.

        Args:
            text (str): text to select
            catch (bool): supress error if fail to select (on by default)
        """
        for _idx, _item in enumerate(self.all_items()):
            if _item.text() == text:
                self.setCurrentRow(_idx)
                return
        if not catch:
            raise ValueError('Failed to select ' + text)

    def selected_data(self, catch=True):
        """Get data from selected item.

        Args:
            catch (bool): no error in exactly one item is not found

        Returns:
            (any): selected data
        """
        _sel = self.selectedItems()
        if not _sel:
            return None
        _item = single(_sel, catch=catch)
        if not _item:
            return None
        return _item.data(Qt.UserRole)

    def selected_datas(self):
        """Get data from selected item.

        Returns:
            (list): selected data
        """
        _sel = self.selectedItems()
        if not _sel:
            return []
        return [_item.data(Qt.UserRole) for _item in _sel]

    def selected_item(self):
        """Obtain currently selected item.

        Returns:
            (QListWidgetItem): selected item
        """
        _sel = self.selectedItems()
        if not _sel:
            return None
        return single(_sel)

    def selected_items(self):
        """Get list of selected items.

        (Provided for symmetry)

        Returns:
            (QListWidgetItem list): selected items
        """
        return self.selectedItems()

    def selected_text(self):
        """Get text from selected item.

        Returns:
            (str): selected text
        """
        _sel = self.selectedItems()
        if not len(_sel) == 1:
            return None
        return single(_sel).text()

    def selected_texts(self):
        """Get list of text from selected items.

        Returns:
            (str list): text from selected items
        """
        return [_item.text() for _item in self.selectedItems()]

    def set_items(self, items, select=None, emit=None, use_empty_marker=True):
        """Clear the contents and apply a new list of items.

        Args:
            items (QListWidgetItem list): items to apply
            select (QListWidgetItem): item to select (by default the first
                item is selected)
            emit (bool): emit changed signal on apply items
            use_empty_marker (bool): in the case of an empty list, disable
                the widget and add a <None> element
        """
        _LOGGER.debug('SET ITEMS %s %s', self, items)
        _LOGGER.debug(' - SELECT %s', select)

        _cur_text = self.selected_text()
        _blocked = self.signalsBlocked()
        _emit = (not _blocked) if emit is None else emit
        _LOGGER.debug(' - EMIT %d (emit=%s, blocked=%d)', _emit, emit, _blocked)

        # Repopulate list
        self.blockSignals(True)
        self.clear()
        _sel_idx = 0
        _sel_idxs = []
        for _idx, _item in enumerate(items):

            self.addItem(_item)

            _text = self.item(_idx).text()
            _data = self.item(_idx).data(Qt.UserRole)

            # Apply selection
            if select:
                if select is _item:
                    _sel_idx = _idx
                elif _data and _data == select:
                    _sel_idx = _idx
                elif isinstance(select, str) and _text == select:
                    _sel_idx = _idx
                elif isinstance(select, (list, set)) and (
                        (_data and _data in select) or
                        _item in select or
                        _text in select):
                    _sel_idxs.append(_idx)
            elif _cur_text and _text == _cur_text:
                _sel_idx = _idx

        # Apply selection
        _LOGGER.debug(' - APPLY SEL %s', _sel_idxs)
        if _sel_idxs:
            self.select_rows(_sel_idxs)
        elif items and select not in ([], EMPTY):
            self.select_row(_sel_idx)

        # Disable and addd <None> marker if empty
        if use_empty_marker:
            self.is_empty = not bool(items)
            self.setEnabled(not self.is_empty)
            self.empty_marker = None
            if not items:
                self.empty_marker = CListWidgetItem('<None>')
                self.addItem(self.empty_marker)

        self.blockSignals(_blocked)
        if _emit:
            self.itemSelectionChanged.emit()

    def set_val(self, val):
        """Apply value to this element.

        Args:
            val (str): text to select
        """
        self.select_text(val)

    def mouseMoveEvent(self, event):
        """Triggered by mouse move.

        Args:
            event (QMouseEvent): triggered event
        """
        _LOGGER.debug('MOUSE MOVE %s', event)
        super().mouseMoveEvent(event)

    def selectAll(self):
        """Select all items."""
        if self.is_empty:
            self.clearSelection()
        else:
            super().selectAll()
