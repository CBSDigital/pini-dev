"""Tools for adding functionality to QListView widget."""

import logging
import operator

from pini.utils import basic_repr, single, EMPTY

from ...q_mgr import QtWidgets, QtGui, Qt, QtCore
from ... import q_utils
from . import qw_base_widget

_LOGGER = logging.getLogger(__name__)


class CListView(QtWidgets.QListView, qw_base_widget.CBaseWidget):
    """Wrapper for QListView widget."""

    save_policy = q_utils.SavePolicy.NO_SAVE

    def __init__(self, *args):
        """Constructor."""
        _LOGGER.debug('CREATE LIST VIEW')
        super().__init__(*args)
        _LOGGER.debug(' - RAN INIT')

        _model = QtGui.QStandardItemModel(self)
        _LOGGER.debug(' - MODEL %s', _model)
        self.setModel(_model)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        self.redraw_items()

    def all_data(self):
        """Retrieve data from all elements.

        Returns:
            (list): all data
        """
        return [_item.get_data() for _item in self.all_items()]

    def all_items(self):
        """Obtain list of all items.

        Returns:
            (QStandardItem list): all items
        """
        _items = []
        for _idx in range(self.model().rowCount()):
            _item = self.model().item(_idx, 0)
            _items.append(_item)
        return _items

    def get_draw_width(self):
        """Calculate width to draw contents in.

        Returns:
            (int): width in pixels
        """
        _vsb = self.verticalScrollBar()
        _draw_width = self.width() - 4
        if _vsb.isVisible():
            _draw_width -= _vsb.width()
        _LOGGER.log(9, ' - GET DRAW WIDTH vsb=%d w=%d, draw_w=%d',
                    _vsb.isVisible(), self.width(), _draw_width)
        return _draw_width

    def get_val(self):
        """Get selected text.

        Returns:
            (str): selected text
        """
        return self.selected_item().text()

    def redraw_items(self):
        """Redraw contents.

        This allows contents to respond dynamically to changes in size
        of this list view.

        Triggered by resize.
        """
        from pini import qt

        _LOGGER.debug('REDRAW ITEMS %s %s', self, self.size())

        # Calculate max item height
        _height = 0
        for _idx, _item in enumerate(self.all_items()):
            _item.redraw()
            _height = max(_height, _item.sizeHint().height())

        # Apply icon size using max height
        _cur_icon_size = self.iconSize()
        _icon_size = qt.to_size(self.get_draw_width(), _height)
        _LOGGER.debug(' - ICON SIZE %s -> %s height=%d visible=%d',
                      _cur_icon_size, _icon_size, _height, self.isVisible())
        if _cur_icon_size.height() == _icon_size.height():
            _LOGGER.debug(' - NO HEIGHT CHANGE - REDRAW NOT NEEDED')
            return
        self.setIconSize(_icon_size)

        # Redraw child items
        _draw_width = self.get_draw_width()
        _LOGGER.debug(' - DRAW WIDTH %d', _draw_width)
        _model = self.model()
        for _idx, _item in enumerate(self.all_items()):
            _size_hint = qt.to_size(_draw_width, _item.height)
            _item.setSizeHint(_size_hint)
            _model.setData(_model.index(_idx, 0), _size_hint, Qt.SizeHintRole)
        for _idx, _item in enumerate(self.all_items()):
            _item.redraw()

    def remove_item(self, item):
        """Remove the given item from the list.

        Args:
            item (QStandardItem): item to remove
        """
        self.model().removeRow(item.row())

    def select(self, obj, replace=True, catch=False):
        """Select the given object or objects.

        Args:
            obj (QStandardItem|any/list): what to select
            replace (bool): replace existing selection
            catch (bool): no error if fail to select
        """
        _LOGGER.debug('SELECT %s %s', obj, self)

        if isinstance(obj, list):
            _LOGGER.debug(' - LIST')
            for _idx, _obj in enumerate(obj):
                self.select(_obj, replace=replace and not _idx)
            return

        if isinstance(obj, QtGui.QStandardItem):
            _LOGGER.debug(' - ITEM')
            self.select_item(obj, replace=replace)
            return

        _all_data = self.all_data()
        _LOGGER.debug(' - ALL DATA %s', _all_data)
        if obj in _all_data:
            _LOGGER.debug(' - USING DATA')
            _idx = _all_data.index(obj)
            _item = self.all_items()[_idx]
            self.select_item(_item, replace=replace)
            return

        if catch:
            return
        raise ValueError(obj)

    def select_data(self, data, catch=True):
        """Select item by its embedded data.

        Args:
            data (any): data to select
            catch (bool): no error on fail to select
        """
        _datas, _items = self.all_data(), self.all_items()
        if data not in _datas:
            if not catch:
                raise ValueError(f'Failed to select {data}')
            return
        self.select_item(_items[_datas.index(data)])

    def select_item(self, item, replace=True):
        """Select the given item.

        Args:
            item (QStandardItem): item to select
            replace (bool): replace existing selection
        """

        # Update selection
        assert isinstance(item, QtGui.QStandardItem)
        _sel = self.selectionModel()
        if replace:
            _sel_model = QtCore.QItemSelectionModel.ClearAndSelect
        else:
            _sel_model = QtCore.QItemSelectionModel.Select
        _sel.setCurrentIndex(item.index(), _sel_model)

        # Make item visible
        self.scrollTo(item.index())

    def select_row(self, idx):
        """Select the given row index.

        Args:
            idx (int): row to select
        """
        _item = self.all_items()[idx]
        self.select_item(_item)

    def selected_data(self, catch=True):
        """Obtain data from currently selected item.

        Args:
            catch (bool): no error if single item not selected

        Returns:
            (any): item data
        """
        return single(self.selected_datas(), catch=catch)

    def selected_datas(self):
        """Obtain data from selected items.

        Returns:
            (list): selected item data
        """
        return [_item.get_data() for _item in self.selected_items()]

    def selected_item(self, catch=True):
        """Obtain currently selected item.

        Args:
            catch (bool): no error if single item not selected

        Returns:
            (QStandardItem): selected item
        """
        return single(self.selected_items(), catch=catch)

    def selected_items(self):
        """Get selected items.

        Returns:
            (QStandardItem list): selected items
        """
        _idxs = self.selectionModel().selectedIndexes()
        _idxs.sort(key=operator.methodcaller('row'))
        return [self.model().item(_idx.row(), 0) for _idx in _idxs]

    def set_items(self, items, select=EMPTY, emit=True):
        """Set current list of items.

        Args:
            items (QStandardItem list): items to add
            select (QStandardItem): item to select
            emit (bool): emit signal on update
        """
        _LOGGER.debug('SET ITEMS %s', items)

        _width = self.get_draw_width()
        _sel_model = self.selectionModel()
        _model = self.model()

        _signals = _sel_model.signalsBlocked()
        _sel_model.blockSignals(True)

        # Populate list
        _model.clear()
        for _idx, _item in enumerate(items):
            _model.appendRow(_item)
            self.setIndexWidget(_item.index(), _item.widget)
            _model.setData(
                _model.index(_idx, 0), _item.sizeHint(), Qt.SizeHintRole)
        self.redraw_items()

        # Apply selection
        if select is EMPTY or (not select and isinstance(select, list)):
            if items:
                self.select(items[0])
        elif select:
            self.select(select, catch=True)
        elif select is None:
            _sel_model.clearSelection()
        else:
            raise ValueError(select)

        _sel_model.blockSignals(_signals)
        if emit:
            _sel_model.selectionChanged.emit(0, 0)

    def set_val(self, val):
        """Apply value to this element.

        Args:
            val (str): text to select
        """
        self.select(val)

    def resizeEvent(self, event=None):
        """Triggered by resize.

        Args:
            event (QResizeEvent): triggered event
        """
        _LOGGER.debug('RESIZE EVENT')
        super().resizeEvent(event)
        if self.model():
            self.redraw_items()
        _LOGGER.debug(' - RESIZE EVENT COMPLETE')

    def __repr__(self):
        return basic_repr(self, self.objectName())
