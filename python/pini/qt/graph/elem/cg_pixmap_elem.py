"""Tools for managing pixmap elements.

This is a graph space element where the pixmap is drawn on each frame.
"""

import logging

from ... import wrapper, q_utils
from ...q_mgr import QtCore, QtGui
from . import cg_basic_elem

_LOGGER = logging.getLogger(__name__)

_DISABLED_TEXT_COL = wrapper.CColor('Black')
_DISABLED_TEXT_COL.setAlphaF(0.4)


class CGPixmapElem(cg_basic_elem.CGBasicElem):
    """A graph space element which draws a pixmap when it is displayed."""

    def __init__(self, label=None, **kwargs):
        """Constructor.

        Args:
            label (str): element label
        """
        super(CGPixmapElem, self).__init__(**kwargs)
        self.label = label

    def g2p(self, obj):
        """Map an object from graph to local pixmap space.

        Args:
            obj (any): object to map

        Returns:
            (any): mapped object
        """
        _obj = obj
        if isinstance(obj, (QtCore.QPointF, QtCore.QPoint)):
            return wrapper.CPointF(
                self.graph.zoom*_obj.x(),
                self.graph.zoom*_obj.y())
        return self.graph.g2p(_obj)

    def _draw_bg(self, pix, rect=None):
        """Draw background (disabled for this subclass).

        Args:
            pix (CPixmap): pixmap to draw on
            rect (QRectF): override draw rectangle
        """
        _over = self._setup_pixmap(rect=rect)
        _rect_p = rect or self.rect_p
        pix.draw_rounded_overlay(
            _over, pos=_rect_p.topLeft(),
            bevel=self.graph.g2p(self.bevel_g))
        return _rect_p

    def _draw_label(self, **kwargs):
        """Handled in draw_bg method."""

    def _setup_pixmap(self, rect=None):
        """Draw this element's pixmap.

        Args:
            rect (QRectF): override draw rectangle

        Returns:
            (QPixmap): element's pixmap (if any)
        """
        _rect_p = rect or self.rect_p
        _size_p = q_utils.to_size(_rect_p.size(), class_=QtCore.QSize)
        _size_g = self.graph.p2g(_size_p)

        _pix = wrapper.CPixmap(_size_p)
        _pix.fill('Transparent')
        self._draw_rounded_rect(
            pix=_pix, pos=(0, 0), size=_size_g, space='graph', anchor='TL',
            col=self.col)
        self.update_pixmap(_pix)

        if self.label:
            _col = _DISABLED_TEXT_COL if not self.enabled else self.text_col
            self._draw_text(
                pix=_pix, text=self.label, pos=_size_g/2, anchor='C', col=_col)

        return _pix

    def update_pixmap(self, pix):
        """Update this element's pixmap.

        (To be implemented in subclass).

        Args:
            pix (CPixmap): pixmap to draw on (in local space)
        """

    def _draw_line(self, pix, point_a, point_b, space='graph'):
        """Draw a line on this element's pixmap.

        Args:
            pix (CPixmap): pixmap to draw on
            point_a (QPointF): start point (in local space)
            point_b (QPointF): end point (in local space)
            space (str): draw space (graph/fr)
        """
        if space == 'fr':
            _pt_a_g = self.f2g(wrapper.CPointF(point_a))
            _pt_b_g = self.f2g(wrapper.CPointF(point_b))
        else:
            raise ValueError(space)
        _pt_a_p = self.g2p(_pt_a_g)
        _pt_b_p = self.g2p(_pt_b_g)
        pix.draw_line(_pt_a_p, _pt_b_p)

    def _draw_overlay(self, pix, over, pos, size, anchor='TL', space='graph'):
        """Draw an overlay on this element's pixmap.

        Args:
            pix (CPixmap): pixmap to draw on
            over (CPixmap): overlay to draw
            pos (QPointF): draw position (in local space)
            size (QSizeF): draw size (in local space)
            anchor (str): overlay anchor
            space (str): draw space (graph/fr)
        """
        _pos = q_utils.to_p(pos, class_=wrapper.CPointF)
        _size = q_utils.to_size(size, class_=wrapper.CSizeF)
        assert isinstance(over, QtGui.QPixmap)
        if space == 'graph':
            _pos_g = _pos
            _size_g = _size
        elif space == 'graph':
            _pos_g = self.f2g(_pos)
            _size_g = self.f2g(_size)
        else:
            raise ValueError(space)
        _pos_p = self.g2p(_pos_g)
        _size_p = self.g2p(_size_g)
        pix.draw_overlay(
            over, pos=_pos_p, size=_size_p, anchor=anchor)

    def _draw_rounded_rect(
            self, pix, pos, size, col, bevel=None, anchor='TL', space='graph'):
        """Draw a rounded rectangle on this element's pixmap.

        All drawing is in local space.

        Args:
            pix (CPixmap): pixmap to draw on
            pos (QPointF): draw position (in local space)
            size (QSizeF): draw size (in local space)
            col (str): rectangle colour
            bevel (float): override bevel
            anchor (str): rectangle anchor
            space (str): draw space (graph/fr)
        """
        _LOGGER.debug('DRAW ROUNDED RECT %s %s', pos, size)
        _pos = q_utils.to_p(pos, class_=wrapper.CPointF)
        _size = q_utils.to_size(size, class_=wrapper.CSizeF)
        if space == 'graph':
            _pos_g = _pos
            _size_g = _size
        else:
            raise ValueError(space)
        _LOGGER.debug(' - POS/SIZE %s %s', _pos_g, _size_g)
        _bevel_g = self.bevel_g if bevel is None else bevel

        _pos_p = self.g2p(_pos_g)
        _size_p = self.g2p(_size_g)
        pix.draw_rounded_rect(
            pos=_pos_p, size=_size_p, bevel=self.graph.g2p(_bevel_g),
            col=col, outline=None, anchor=anchor)

    def _draw_text(
            self, pix, text, pos, size=None, anchor='TL', space='graph',
            col=None):
        """Draw text on this element's pixmap.

        Args:
            pix (CPixmap): pixmap to draw on
            text (str): text to write
            pos (QPointF): draw position (in local space)
            size (float): text size (in local space)
            anchor (str): text anchor
            space (str): draw space (graph/fr)
            col (QColor): text colour
        """
        _pos = q_utils.to_p(pos, class_=wrapper.CPointF)
        if space == 'fr':
            _pos_g = self.f2g(_pos)
            _LOGGER.debug(' - MAPPED %s -> %s', _pos, _pos_g)
        elif space == 'graph':
            _pos_g = _pos
        else:
            raise ValueError(space)
        _pos_p = self.g2p(_pos_g)
        _size = self.g2p(size or self.text_size_g)
        pix.draw_text(text, pos=_pos_p, size=_size, anchor=anchor, col=col)
