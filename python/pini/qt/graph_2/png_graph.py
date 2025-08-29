"""Tools for managing to node graph object."""

import logging

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

    def keyPressEvent(self, event):
        """Triggered by key press.

        Args:
            event (QEvent): event
        """
        _LOGGER.info('KEY PRESS %s', event)
        if event.text() == 'f':
            self.fit_view()
        else:
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
