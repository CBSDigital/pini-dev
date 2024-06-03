"""Tools for managing graph space elements."""

# pylint: disable=assignment-from-none,too-many-instance-attributes

import logging

from pini.utils import strftime, basic_repr, EMPTY, val_map

from ... import wrapper, q_utils
from ...q_mgr import QtGui, QtCore, Qt
from .. import c_graph_elem, c_graph_space

_LOGGER = logging.getLogger(__name__)

_SEL_PEN_W = 6
_SEL_PEN = QtGui.QPen('Yellow')
_SEL_PEN.setWidthF(_SEL_PEN_W)

_SEL_COL = wrapper.CColor('White')
_SEL_COL.setAlphaF(0.2)


class CGBasicElem(c_graph_elem.CGraphElemBase):
    """Base class for any graph space element."""

    graph = None
    visible = True

    # Drag controls
    drag_end_g = None
    drag_end_p = None
    drag_start_g = None
    drag_start_p = None
    drag_vect_g = None
    drag_anchor_p = None
    drag_target_p = None
    drag_vect_p = None

    local_pos_g = None
    size_g = None

    def __init__(
            self, parent, name=None, pos=(0, 0), size=(100, 100), col='Yellow',
            anchor='C', label=EMPTY, style='rounded_rect', draggable=False,
            saveable=False, text_size=10, bevel=5, callback=None, enabled=True,
            selectable=False, space='graph', level=None, text_col='Black'):
        """Constructor.

        Args:
            parent (CGraphElem/CGraphSpace): parent element
            name (str): unique name for element
            pos (QPoint): element position
            size (QSize): element size
            col (str): element colour
            anchor (str): element rectangle anchor
            label (str): element label
            style (str): element draw style (dot/rounded_rect)
            draggable (bool): whether element is draggable
            saveable (bool): whether element settings are saveable
            text_size (int): text size (in graph space)
            bevel (int): edge bevel (in graph space)
            callback (fn): callback to execute on click
            enabled (bool): enabled state of element
            selectable (bool): whether this element is selectable
            space (str): space for pos/size (graph/fr)
            level (float): force level for this element (higher elements are
                drawn on top, and take click in precedence to lower elements)
            text_col (str): colour for text
        """

        # Setup name/label
        _name = name
        if not _name:
            _base = type(self).__name__.strip('_')
            _LOGGER.debug('BASE %s', _base)
            _idx = len(parent.find_elems(head=_base))
            _name = _base+str(_idx)
            _LOGGER.debug(' - NAME %s', _name)
        assert '.' not in _name
        self.name = _name
        self.label = label if label is not EMPTY else self.name

        self.col = q_utils.to_col(col)
        self.text_col = q_utils.to_col(text_col)

        self.anchor = anchor
        self.style = style
        self.callback = callback
        self.selected = False

        self.draggable = draggable
        self.saveable = saveable
        self.selectable = selectable
        self.enabled = enabled

        self.text_size_g = text_size
        self.bevel_g = bevel

        self.elems = []

        self._apply_parent(parent=parent, level=level)
        self._apply_tfm(pos=pos, size=size, space=space)

    def _apply_parent(self, parent, level):
        """Apply parenting.

        Args:
            parent (CGraphElem/CGraphSpace): parent element
            level (float): force level for this element
        """
        self.parent = None
        if isinstance(parent, CGBasicElem):
            self.parent = parent
            self.level = self.parent.level + 10
            self.parent.append_child_elem(self)
            self.graph = parent.graph
            assert self.graph is self.parent.graph
        elif isinstance(parent, c_graph_space.CGraphSpace):
            self.level = 0
            parent.append_child_elem(self)
            self.graph = parent
        else:
            raise ValueError(parent)

        if level is not None:
            self.level = level

    def _apply_tfm(self, pos, size, space):
        """Apply pos/size transform.

        Args:
            pos (QPoint): element position
            size (QSize): element size
            space (str): space for pos/size (graph/fr)
        """
        _pos = q_utils.to_p(pos, class_=wrapper.CPointF)
        _size = q_utils.to_size(size, class_=wrapper.CSizeF)
        _LOGGER.debug(' - APPLY POS/SIZE %s %s %s', space, _pos, _size)
        if space == 'graph':
            self.local_pos_g = _pos
            self.size_g = _size
        elif space == 'fr':
            assert _size.width() < 1
            assert _size.height() < 1
            self.local_pos_g = self.parent.f2g(_pos)
            self.size_g = self.parent.f2g(_size)
        else:
            raise ValueError(space)
        assert isinstance(self.size_g, wrapper.CSizeF)

    @property
    def full_name(self):
        """Obtain full element name (including parent name if any).

        Returns:
            (str): full name
        """
        if not self.parent:
            return self.name
        return '{}.{}'.format(self.parent.full_name, self.name)

    @property
    def pos_g(self):
        """Obtain graph position.

        Returns:
            (QPointF): graph position
        """
        _pos = self.local_pos_g
        if self.parent:
            _pos = wrapper.CPointF(_pos) + self.parent.rect_g.topLeft()
        return _pos

    @property
    def pos_p(self):
        """Obtain pixmap position.

        Returns:
            (QPointF): pixmap position
        """
        return self.graph.g2p(self.pos_g)

    @property
    def rect_g(self):
        """Obtain graph rectangle.

        Returns:
            (QRectF): graph rectangle
        """
        assert isinstance(self.size_g, (QtCore.QSize, QtCore.QSizeF))
        return q_utils.to_rect(
            pos=self.pos_g, size=self.size_g, anchor=self.anchor,
            class_=QtCore.QRectF)

    @property
    def rect_p(self):
        """Obtain graph rectangle.

        Returns:
            (QRectF): graph rectangle
        """
        return self.graph.g2p(self.rect_g)

    @property
    def size_p(self):
        """Obtain pixmap size.

        Returns:
            (QSizeF): pixmap size
        """
        return self.graph.g2p(self.size_g)

    def f2g(self, obj):
        """Map the given object from fraction to graph space.

        Args:
            obj (QPointF): object to map

        Returns:
            (QPointF): mapped object
        """
        if isinstance(obj, QtCore.QPointF):
            _x_g = val_map(obj.x(), out_max=self.rect_g.width())
            _y_g = val_map(obj.y(), out_max=self.rect_g.height())
            return q_utils.to_p((_x_g, _y_g), class_=wrapper.CPointF)
        if isinstance(obj, QtCore.QSizeF):
            _w_g = val_map(obj.width(), out_max=self.rect_g.width())
            _h_g = val_map(obj.height(), out_max=self.rect_g.height())
            _result = q_utils.to_size(_w_g, _h_g, class_=wrapper.CSizeF)
            _LOGGER.info(' - MAPPED SIZE %s -> %s', obj, _result)
            return _result
        raise ValueError(obj)

    def get_settings(self):
        """Read settings for this element.

        Returns:
            (dict): saveable settings
        """
        return {}

    def set_settings(self, settings):
        """Apply settings to this element.

        Args:
            settings (dict): settings to apply
        """
        _pos = _size = None
        if 'pos' in settings:
            _pos = wrapper.CPointF(*settings['pos'])
            self.local_pos_g = _pos
        if 'size' in settings:
            _size = wrapper.CSizeF(*settings['size'])
            self.size_g = _size
        _LOGGER.debug(' - LOAD SETTING %s %s %s', self, _pos, _size)
        self.resizeEvent()

    def contains(self, pos_g):
        """Check whether this element's rectangle contains the given point.

        NOTE: this is applied in graph space.

        Args:
            pos_g (QPointF): point to test

        Returns:
            (bool): whether point inside
        """
        return self.rect_g.contains(pos_g)

    def reset(self):
        """Reset this element."""
        _LOGGER.info('RESET %s', self)
        for _child in self.elems:
            _child.reset()

    def set_enabled(self, enabled=True):
        """Set enabled status of this element.

        Args:
            enabled (bool): enabled state
        """
        self.enabled = enabled

    def draw(self, pix):
        """Draw this element on the given pixmap.

        Args:
            pix (QPixmap): pixmap to draw on
        """
        _LOGGER.log(9, 'DRAW %s', self)

        _rect_p = self._draw_bg(pix)
        if self.label:
            self._draw_label(pix=pix, rect=_rect_p)
        self._draw_children(pix)
        if self.selected:
            self._draw_selection(pix, rect=_rect_p)

    def _draw_bg(self, pix):
        """Draw this element's background.

        Args:
            pix (CPixmap): pixmap to draw on
        """
        _rect_p = self.graph.g2p(self.rect_g)
        if self.style == 'rounded_rect':
            pix.draw_rounded_rect(
                col=self.col,
                pos=_rect_p.topLeft(), size=_rect_p.size(), anchor='TL',
                outline=None, bevel=self.graph.g2p(self.bevel_g))
        elif self.style == 'dot':
            pix.draw_dot(
                col=self.col,
                pos=_rect_p.center(), radius=_rect_p.width()/2,
                anchor='C', outline=None)
        else:
            raise NotImplementedError(self.style)
        return _rect_p

    def _draw_label(self, pix, rect=None):
        """Draw label for this element.

        Args:
            pix (CPixmap): pixmap to draw on
            rect (CRectF): override draw rect (in pixmap space)
        """
        _rect_p = rect or self.rect_p
        pix.draw_text(
            self.label, anchor='C',
            size=self.graph.g2p(self.text_size_g),
            pos=_rect_p.center())

    def _draw_children(self, pix):
        """Draw children of this element.

        Args:
            pix (CPixmap): pixmap to draw on
        """
        for _child in self.elems:
            if not _child.visible:
                continue
            _child.draw(pix)

    def _draw_selection(self, pix, rect=None):
        """Draw selection highlighting for this element.

        Args:
            pix (CPixmap): pixmap to draw on
            rect (CRectF): override draw rect (in pixmap space)
        """
        _rect_p = rect or self.rect_p
        _offs = _SEL_PEN_W*0.45
        _rect_p = q_utils.to_rect(
            pos=_rect_p.topLeft() + q_utils.to_p(_offs, _offs),
            size=_rect_p.size() - q_utils.to_size(_offs*2))
        pix.draw_rounded_rect(
            col=_SEL_COL, outline=_SEL_PEN,
            pos=_rect_p.topLeft(), size=_rect_p.size(), anchor='TL',
            bevel=self.graph.g2p(self.bevel_g))

    def move(self, vector):
        """Move this control.

        Args:
            vector (CPointF): relative move to apply
        """
        _LOGGER.info('APPLY MOVE %s %s', self, vector)
        _vect = q_utils.to_p(vector)
        self.mousePressEvent(event=None)
        self.local_pos_g += _vect
        self.mouseMoveEvent(event=None)
        self.graph.redraw()

    def mousePressEvent(self, event):
        """Triggered by mouse press.

        Args:
            event (QMouseEvent): triggered event
        """
        _LOGGER.debug(
            'MOUSE PRESS %s t=%s sel=%d drag=%d', self, strftime('%H:%M:%S'),
            self.selectable, self.draggable)

        if not self.enabled:
            return event

        _pos = event.pos() if event else wrapper.CPointF()
        self.drag_start_p = self.drag_end_p = _pos
        self.drag_start_g = self.drag_end_g = self.graph.p2g(_pos)
        self.drag_vect_g = None

        if not self.draggable:
            _LOGGER.debug(' - APPLY SELECTION')
            self._apply_selection(event)

        if self.callback and event.button() == Qt.LeftButton:
            _LOGGER.info(' - EXEC CALLBACK %s', self.callback)
            self.callback()
            return None

        return event

    def mouseMoveEvent(self, event=None):
        """Triggered by mouse move.

        Args:
            event (QMouseEvent): triggered event
        """
        assert self.draggable

        if event:
            self.drag_end_p = event.pos()
            self.drag_vect_p = wrapper.CVector2D(
                self.drag_end_p - self.drag_start_p)
            self.drag_end_g = self.graph.p2g(event.pos())
            self.drag_vect_g = self.graph.p2g(self.drag_vect_p)

        _LOGGER.debug(
            'MOUSE MOVE %s %s %s %s', self, strftime('%H%M%S'),
            self.drag_vect_p, self.drag_vect_g)

        return event

    def mouseReleaseEvent(self, event, update_selection=True):
        """Triggered by mouse release.

        Args:
            event (QMouseEvent): triggered event
            update_selection (bool): whether to update selection state
        """
        _LOGGER.debug(
            'MOUSE RELEASE %s t=%s v=%s', self, strftime('%H:%M:%S'),
            self.drag_vect_g)
        self.drag_start_p = self.drag_end_p = None

        if update_selection and not self.drag_vect_g:
            self._apply_selection(event)

        return event

    def _apply_selection(self, event):
        """Apply selection policy.

        NOTE: for draggable elements this is applied on mouse release in the
        case of no drag; otherwise it is applied on mouse press.

        Args:
            event (QMouseEvent): triggered event
        """
        if self.selectable and event.button() is Qt.LeftButton:
            _sel = self.selected
            _ctrl = event.modifiers() == Qt.ControlModifier
            if not _ctrl:
                self.graph.clear_selection()
            if not _sel:
                self.selected = not self.selected
            _LOGGER.info(' - TOGGLE SELECTED %s ctrl=%d', self.selected, _ctrl)

    def resizeEvent(self, event=None):
        """Triggered by resize.

        Args:
            event (QResizeEvent): triggered event
        """
        return event

    def __repr__(self):
        return basic_repr(self, self.full_name)
