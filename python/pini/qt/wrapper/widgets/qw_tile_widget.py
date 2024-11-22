"""Tools for managing a CTileWidget."""

import logging
import random

from . import qw_list_widget
from ...q_utils import to_size, to_p
from ...q_mgr import QtWidgets, Qt

_LOGGER = logging.getLogger(__name__)


class CTileWidget(qw_list_widget.CListWidget):
    """Wrapper for QListWidget used for displaying tiles."""

    def __init__(self, parent=None, grid_size=100):
        """Constructor.

        Args:
            parent (QWidget): parent widget
            grid_size (int): tile grid size
        """
        super().__init__(parent=parent)

        self.setResizeMode(QtWidgets.QListView.Adjust)
        self.setWrapping(True)
        self.setSpacing(5)
        self.setFlow(QtWidgets.QListView.LeftToRight)
        self.setItemAlignment(Qt.AlignHCenter)
        self.setMouseTracking(True)

        self.set_grid_size(grid_size)

    def set_grid_size(self, size):
        """Set grid size file this widget and its items.

        Args:
            size (QSize): size to apply
        """
        self.grid_size = to_size(size)
        self.setGridSize(self.grid_size)
        self.setIconSize(self.grid_size)
        for _item in self.all_items():
            _item.set_size(self.grid_size)
            _item.redraw()

    def set_items(
            self, items, select=None, emit=None, use_empty_marker=True,
            update_labels=False):
        """Set contents of this widget.

        If no name/label is set then incremental names are applied. If no colour
        is set then a random colour is assigned.

        Args:
            items (CTileWidgetItem list): items to fill list with
            select (CTileWidgetItem): item to select (by default the first
                item is selected)
            emit (bool): emit changed signal on apply items
            use_empty_marker (bool): in the case of an empty list, disable
                the widget and add a <None> element
            update_labels (bool): update item labels
        """

        # Set up random default colours
        _rand = random.Random()
        _rand.seed(1)
        _cols = ['Red', 'Green', 'Blue', 'Pink', 'Yellow']

        # Apply name/label/colour
        for _idx, _item in enumerate(items, start=1):
            _item.name = _item.name or f'tile{_idx:02}'
            if update_labels:
                _item.label = _item.label or _item.name
            _item.col = _item.col or _rand.choice(_cols)
            _item.redraw()

        super().set_items(
            items, select=select, emit=emit, use_empty_marker=use_empty_marker)

    def visible_items(self):
        """Find visible items in this widget.

        Returns:
            (CTileWidgetItem list): visible items
        """
        _LOGGER.debug('VISIBLE ITEMS')

        _all_items = self.all_items()
        _LOGGER.debug(' - ALL ITEMS %s %s', type(_all_items), _all_items)

        # Get index of first visible item
        _first_m_idx = self.indexAt(to_p(0, 5))
        _first_idx = _first_m_idx.row()
        _LOGGER.debug(' - FIRST %s %s', _first_idx, _first_m_idx)

        # Get index of last visible item
        _last_m_idx = self.indexAt(
            to_p(self.width() - self.grid_size.width(), self.height() - 5))
        _last_idx = _last_m_idx.row() if _last_m_idx.row() != -1 else None
        _LOGGER.debug(' - LAST %s %s', _last_idx, _last_m_idx)

        # Build items list
        if _last_idx is not None:
            _vis_items = _all_items[_first_idx: _last_idx + 1]
        else:
            _vis_items = _all_items[_first_idx:]

        return _vis_items

    def mouseMoveEvent(self, event):
        """Triggered by mouse move.

        This applies x_scroll value to any widget the mouse is over, to
        accommodate animationed thumbnails.

        Args:
            event (QMouseEvent): triggered event
        """
        _item = self.itemAt(event.pos())
        if not _item:
            return

        _LOGGER.debug('MOUSE MOVE %s', _item)
        _model = self.model()
        _row = self.row(_item)
        _rect = self.visualRect(_model.index(_row))
        _x_scroll = event.pos().x() - _rect.left()
        _LOGGER.debug(' - SCROLL %s %s', _rect, _x_scroll)
        _item.set_x_scroll(_x_scroll)
