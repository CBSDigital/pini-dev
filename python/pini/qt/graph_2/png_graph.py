"""Tools for managing to node graph object."""

import logging

from pini.utils import single, wrap_fn

from ..q_mgr import QtWidgets, QtGui, Qt
from .. import q_utils, wrapper

from . import png_node

_LOGGER = logging.getLogger(__name__)


class PNGNodeGraph(QtWidgets.QGraphicsView):
    """A graphics view which displays nodes."""

    def __init__(self, parent=None, base=None):
        """Constructor.

        Args:
            parent (QWidget): parent widget
            base (QRect): base region
        """
        _LOGGER.info('INIT LSUNodeGraph parent=%s', parent)
        super().__init__(parent)

        self.scene = QtWidgets.QGraphicsScene()
        _LOGGER.info(' - SET SCENE %s', self.scene)
        self.setScene(self.scene)

        self.setDragMode(QtWidgets.QGraphicsView.RubberBandDrag)
        self.setRenderHint(QtGui.QPainter.Antialiasing)
        self.setTransformationAnchor(QtWidgets.QGraphicsView.NoAnchor)
        self.setViewportUpdateMode(QtWidgets.QGraphicsView.FullViewportUpdate)
        self.setInteractive(True)
        self.setDragMode(QtWidgets.QGraphicsView.ScrollHandDrag)

        self.base_r = base or q_utils.to_rect((0, 0), (1920, 1080))
        self.base = png_node.PNGNode(
            scene=self.scene, name='Base',
            col=wrapper.CColor('Grey', alpha=0.1),
            rect=self.base_r)

        self._shortcuts = {}
        self.add_shortcut('a', wrap_fn(self.fit_view, mode='all'))
        self.add_shortcut('f', self.fit_view)

    def add_shortcut(self, key, func):
        """Add graph shortcut.

        Args:
            key (str): shortcut key
            func (fn): shotcut function
        """
        self._shortcuts[key] = func

    def fit_view(self, mode='sel', over=1.05):
        """Fit scene view to nodes.

        Args:
            mode (str): fit mode
                sel - selected node
                all - all nodes
            over (float): overscan value
        """
        _LOGGER.info('FIT VIEW')
        if mode == 'sel':
            _sel = self.scene.selectedItems()
            if _sel:
                _LOGGER.info(' - SEL NODES %s', _sel)
                _fit = _sel[0].rect()
                for _item in _sel[1:]:
                    _fit |= _sel.rect()
            else:
                _fit = self.scene.itemsBoundingRect()
        elif mode == 'all':
            _fit = self.scene.itemsBoundingRect()
        else:
            raise ValueError(mode)
        _LOGGER.info(' - FIT RECT %s', _fit)

        self.fitInView(_fit, Qt.KeepAspectRatio)
        self.scale(1 / over)

    def flush(self):
        """Flush all items from the graph."""
        for _item in self.scene.items():
            if _item is self.base:
                continue
            self.scene.removeItem(_item)

    def scale(self, factor, anchor=None):
        """Scale the current scene.

        Args:
            factor (float): scale factor to apply
            anchor (QPoint): scale anchor
        """
        _LOGGER.debug(' - APPLY SCALE %.2f', factor)

        # Set up anchor in scene space
        _anchor_pos_w = anchor
        if not _anchor_pos_w:
            _anchor_pos_w = self.rect().center()
        _LOGGER.debug('   - ANCHOR POS W %s', _anchor_pos_w)
        _start_pos_s = self.mapToScene(_anchor_pos_w)

        super().scale(factor, factor)

        # Offset so anchor remains in same place
        _end_pos_s = self.mapToScene(_anchor_pos_w)
        _d_pos_s = _end_pos_s - _start_pos_s
        _LOGGER.debug('   - POS S %s -> %s', _start_pos_s, _end_pos_s)
        _LOGGER.debug('   - D POS S %s', _d_pos_s)
        self.translate(_d_pos_s.x(), _d_pos_s.y())

    def select_item(self, item):
        """Select an item.

        Args:
            item (PNGNode): item to select
        """
        self.scene.clearSelection()
        item.setSelected(True)

    def selected_item(self):
        """Obtain selected item from the graph.

        Returns:
            (QGraphicsRectItem|None): item (if any)
        """
        return single(self.scene.selectedItems(), catch=True)

    def get_tfm_t(self):
        """Get value of this graph's transformation.

        Returns:
            (float tuple): transform matrix values
        """
        _tfm = self.transform()

        _vals = []
        for _x in range(1, 4):
            for _y in range(1, 4):
                _name = f'm{_x}{_y}'
                _func = getattr(_tfm, _name)
                _val = _func()
                _vals.append(_val)
        return tuple(_vals)

    def get_view_rect(self):
        """Get view rect.

        Returns:
            (QRectF): view rect
        """
        _rect_v = self.rect()
        return self.mapToScene(_rect_v).boundingRect()

    def set_tfm_t(self, tfm):
        """Set viewport transform from tuple.

        Args:
            tfm (tuple): transform tuple
        """
        _tfm = QtGui.QTransform(*tfm)
        self.setTransform(_tfm)

    def keyPressEvent(self, event):
        """Triggered by key press.

        Args:
            event (QEvent): event
        """
        _LOGGER.debug('KEY PRESS %s', event)

        _focus_item = self.scene.focusItem()
        _blocks = getattr(_focus_item, 'blocks_key_press', False)
        _LOGGER.debug(' - FOCUS %s blocks=%d', _focus_item, _blocks)
        if _blocks:
            _LOGGER.debug(' - KEY PRESS BLOCKED')

        if not _blocks:
            _key_s = QtGui.QKeySequence(event.key()).toString()
            if _key_s in self._shortcuts:
                self._shortcuts[_key_s]()

        super().keyPressEvent(event)

    def wheelEvent(self, event):
        """Mouse wheel event.

        Args:
            event (QEvent): event
        """
        _LOGGER.debug('WHEEL EVENT')

        _factor = 1.2
        if event.angleDelta().y() < 0:
            _factor = 1.0 / _factor

        self.scale(_factor, anchor=event.pos())
