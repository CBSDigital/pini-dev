"""Tools for managing stretch elements."""

# pylint: disable=too-many-instance-attributes

import logging

from ... import wrapper, q_utils
from ...q_mgr import QtCore

from . import cg_move_elem, cg_stretch_ctrl

_LOGGER = logging.getLogger(__name__)


class CGStretchElem(cg_move_elem.CGMoveElem):
    """An element with built in stretch controls."""

    def __init__(self, ctrl_w=10, lock=None, **kwargs):
        """Constructor.

        NOTES:

         - the stretch controls are transparent but are drawn on the pixmap
         - stretch controls are in world space and are not children of this

        Args:
            ctrl_w (int): control width
            lock (str): axis lock (H/V)
        """
        super(CGStretchElem, self).__init__(lock=lock, **kwargs)

        self.ctrl_col = self.col.whiten(0.5)

        _col = wrapper.CColor("Transparent")
        self.left_ctrl_col = self.right_ctrl_col = None
        self.ctrl_w = ctrl_w

        if lock != 'H':
            self.left_ctrl = self._build_left_ctrl(col=_col)
            self.right_ctrl = self._build_right_ctrl(col=_col)
        else:
            self.left_ctrl = self.right_ctrl = None

        if lock != 'V':
            self.top_ctrl = self._build_top_ctrl(col=_col)
            self.bottom_ctrl = self._build_bottom_ctrl(col=_col)
        else:
            self.top_ctrl = self.bottom_ctrl = None

        self.ctrls = tuple(filter(bool, [
            self.top_ctrl, self.bottom_ctrl, self.left_ctrl, self.right_ctrl]))

    def _build_left_ctrl(self, col='Transparent', class_=None):
        """Build left stretch control.

        Args:
            col (str): control colour
            class_ (class): override control class

        Returns:
            (CGStretchCtrl): left stretch control
        """
        _class = class_ or cg_stretch_ctrl.CGStretchCtrl
        return _class(
            pos=self._to_left_ctrl_pos(),
            size=self._to_horiz_ctrl_size(),
            enabled=self.enabled,
            parent=self.graph, anchor='TL', col=col, bevel=1,
            limit='x_max', level=self.level+1, lock='V',
            name=self.name+'Left', stretch=self)

    def _build_right_ctrl(self, col='Transparent', class_=None):
        """Build right stretch control.

        Args:
            col (str): control colour
            class_ (class): override control class

        Returns:
            (CGStretchCtrl): right stretch control
        """
        _class = class_ or cg_stretch_ctrl.CGStretchCtrl
        return _class(
            pos=self._to_right_ctrl_pos(),
            size=self._to_horiz_ctrl_size(),
            enabled=self.enabled,
            parent=self.graph, anchor='TR', col=col, bevel=1,
            limit='x_min', level=self.level+1, lock='V',
            name=self.name+'Right', stretch=self)

    def _build_top_ctrl(self, col='Transparent', class_=None):
        """Build top stretch control.

        Args:
            col (str): control colour
            class_ (class): override control class

        Returns:
            (CGStretchCtrl): top stretch control
        """
        _class = class_ or cg_stretch_ctrl.CGStretchCtrl
        return _class(
            pos=self._to_top_ctrl_pos(),
            size=self._to_vert_ctrl_size(),
            enabled=self.enabled,
            parent=self.graph, anchor='TL', col=col, bevel=1,
            limit='y_max', level=self.level+1, lock='H',
            name=self.name+'Top', stretch=self)

    def _build_bottom_ctrl(self, col='Transparent', class_=None):
        """Build bottom stretch control.

        Args:
            col (str): control colour
            class_ (class): override control class

        Returns:
            (CGStretchCtrl): bottom stretch control
        """
        _class = class_ or cg_stretch_ctrl.CGStretchCtrl
        return _class(
            pos=self._to_bottom_ctrl_pos(),
            size=self._to_vert_ctrl_size(),
            enabled=self.enabled,
            parent=self.graph, anchor='BL', col=col, bevel=1,
            limit='y_min', level=self.level+1, lock='H',
            name=self.name+'Bottom', stretch=self)

    def _to_bottom_ctrl_pos(self):
        """Obtain bottom control position.

        Returns:
            (CPointF): position
        """
        return wrapper.CPointF(
            self.rect_g.bottomLeft()+q_utils.to_p(self.ctrl_w*1.5, 0))

    def _to_left_ctrl_pos(self):
        """Obtain left control position.

        Returns:
            (CPointF): position
        """
        return wrapper.CPointF(
            self.rect_g.topLeft()+q_utils.to_p(0, self.ctrl_w*1.5))

    def _to_right_ctrl_pos(self):
        """Obtain right control position.

        Returns:
            (CPointF): position
        """
        return wrapper.CPointF(
            self.rect_g.topRight()+q_utils.to_p(0, self.ctrl_w*1.5))

    def _to_top_ctrl_pos(self):
        """Obtain top control position.

        Returns:
            (CPointF): position
        """
        return wrapper.CPointF(
            self.rect_g.topLeft()+q_utils.to_p(self.ctrl_w*1.5, 0))

    def _to_horiz_ctrl_size(self):
        """Obtain size for horizontal controls.

        Returns:
            (QSizeF): size
        """
        return wrapper.CSizeF(self.ctrl_w, self.rect_g.height()-self.ctrl_w*3)

    def _to_vert_ctrl_size(self):
        """Obtain size for vertical controls.

        Returns:
            (QSizeF): size
        """
        return wrapper.CSizeF(self.rect_g.width()-self.ctrl_w*3, self.ctrl_w)

    def apply_stretch_update(self, ctrl=None):
        """Apply a pos/size update.

        Args:
            ctrl (CGStretchCtrl): control triggering the update (if any)
        """
        self._update_geo(ctrl=ctrl)
        self._update_unmoved_ctrls(ctrl=ctrl)

    def _update_geo(self, ctrl):
        """Update this element's geo to match ctrl being moved.

        Args:
            ctrl (CGStretchCtrl): control triggering the update (if any)
        """
        _left = self.rect_g.left()
        _top = self.rect_g.top()
        _right = self.rect_g.right()
        _bottom = self.rect_g.bottom()

        # Read dimensions from controls
        if self.bottom_ctrl and ctrl is self.bottom_ctrl:
            _LOGGER.debug(' - UPDATE BOTTOM %s', ctrl)
            _bottom = self.bottom_ctrl.rect_g.bottom()
        elif self.left_ctrl and ctrl is self.left_ctrl:
            _LOGGER.debug(' - UPDATE LEFT %s', ctrl)
            _left = self.left_ctrl.rect_g.left()
        elif self.right_ctrl and ctrl is self.right_ctrl:
            _LOGGER.debug(' - UPDATE RIGHT %s', ctrl)
            _right = self.right_ctrl.rect_g.right()
        elif self.top_ctrl and ctrl is self.top_ctrl:
            _LOGGER.debug(' - UPDATE TOP %s', ctrl)
            _top = self.top_ctrl.rect_g.top()
        elif ctrl is None:
            pass
        else:
            raise ValueError(ctrl)

        _pos = wrapper.CPointF(_left, _top)
        _size = wrapper.CSizeF(_right-_left, _bottom-_top)
        _rect = QtCore.QRectF(_pos, _size)
        if self.anchor == 'C':
            self.local_pos_g = wrapper.CPointF(_rect.center())
        elif self.anchor == 'TL':
            self.local_pos_g = _pos
        else:
            raise ValueError(self.anchor)
        self.size_g = _size

    def _update_unmoved_ctrls(self, ctrl):
        """Update/resize unmoved ctrls to respond to stretch update.

        Args:
            ctrl (CGStretchCtrl): control triggering the update (if any)
        """
        if self.bottom_ctrl and ctrl is not self.bottom_ctrl:
            self.bottom_ctrl.local_pos_g = self._to_bottom_ctrl_pos()
            self.bottom_ctrl.size_g = self._to_vert_ctrl_size()
        if self.left_ctrl and ctrl is not self.left_ctrl:
            self.left_ctrl.local_pos_g = self._to_left_ctrl_pos()
            self.left_ctrl.size_g = self._to_horiz_ctrl_size()
        if self.right_ctrl and ctrl is not self.right_ctrl:
            self.right_ctrl.local_pos_g = self._to_right_ctrl_pos()
            self.right_ctrl.size_g = self._to_horiz_ctrl_size()
        if self.top_ctrl and ctrl is not self.top_ctrl:
            self.top_ctrl.local_pos_g = self._to_top_ctrl_pos()
            self.top_ctrl.size_g = self._to_vert_ctrl_size()

    def update_pixmap(self, pix):
        """Draw this element's pixmap.

        Args:
            pix (CPixmap): pixmap to draw on
        """
        _col = self.ctrl_col
        if self.left_ctrl:
            _pos_g = self.left_ctrl.rect_g.topRight() - self.rect_g.topLeft()
            self._draw_rounded_rect(
                pix=pix, pos=_pos_g,
                size=self._to_horiz_ctrl_size()*wrapper.CSizeF(2, 1),
                col=self.left_ctrl_col or _col, anchor='TR')
        if self.right_ctrl:
            _pos_g = self.right_ctrl.rect_g.topLeft() - self.rect_g.topLeft()
            self._draw_rounded_rect(
                pix=pix, pos=_pos_g,
                size=self._to_horiz_ctrl_size()*wrapper.CSizeF(2, 1),
                col=self.right_ctrl_col or _col, anchor='TL')
        if self.top_ctrl:
            _pos_g = self.top_ctrl.rect_g.bottomLeft() - self.rect_g.topLeft()
            self._draw_rounded_rect(
                pix=pix, pos=_pos_g,
                size=self._to_vert_ctrl_size()*wrapper.CSizeF(1, 2),
                col=_col, anchor='BL')
        if self.bottom_ctrl:
            _pos_g = self.bottom_ctrl.rect_g.topLeft() - self.rect_g.topLeft()
            self._draw_rounded_rect(
                pix=pix, pos=_pos_g,
                size=self._to_vert_ctrl_size()*wrapper.CSizeF(1, 2),
                col=_col, anchor='TL')

    # def _draw_children(self, pix):
    #     """Draw children of this element.

    #     Children outside the boundaries of this widget are hidden.

    #     Args:
    #         pix (CPixmap): pixmap to draw on
    #     """
    #     _LOGGER.info('DRAW CHILDREN %s', self)
    #     for _child in self.find_elems():
    #         _child.visible = self.rect_g.intersects(_child.rect_g)
    #         _LOGGER.info(
    #             ' - CHILD %s %d contains=%d intersects=%d',
    #             _child, _child.visible,
    #             self.rect_g.contains(_child.rect_g),
    #             self.rect_g.intersects(_child.rect_g))
    #     super(CGStretchElem, self)._draw_children(pix)

    def get_settings(self):
        """Read settings for this element.

        Returns:
            (dict): saveable settings
        """
        _settings = super(CGStretchElem, self).get_settings()

        # Get size
        _size = list(self.size_g.to_tuple())
        if self.lock == 'V':
            _size[1] = None
        elif self.lock == 'H':
            _size[0] = None
        elif self.lock is True:
            _size = None
        elif self.lock is False:
            pass
        else:
            raise NotImplementedError(self.lock)
        _settings['size'] = _size

        return _settings

    def reset(self):
        """Reset this element."""
        super(CGStretchElem, self).reset()
        self.size_g = self.size_g_default
        self.apply_stretch_update()

    def set_move_limits(self, min_=None, max_=None):
        """Set movement limits for this control.

        Args:
            min_ (QPointF): minimum position
            max_ (QPointF): maximum position
        """
        super(CGStretchElem, self).set_move_limits(min_=min_, max_=max_)
        for _ctrl in self.ctrls:
            _ctrl.set_move_limits(min_=min_, max_=max_)

    def set_enabled(self, enabled=True):
        """Set enabled status of this element.

        Args:
            enabled (bool): enabled state
        """
        super(CGStretchElem, self).set_enabled(enabled)
        for _ctrl in self.ctrls:
            _ctrl.enabled = enabled

    def mouseMoveEvent(self, event=None):
        """Triggered by mouse move.

        Args:
            event (QMouseEvent): triggered event
        """
        _event = super(CGStretchElem, self).mouseMoveEvent(event)
        self.apply_stretch_update()
        return _event

    def resizeEvent(self, event=None, ctrl=None, block_callback=False):
        """Triggered by resize.

        Args:
            event (QResizeEvent): triggered event
            ctrl (CGStretchCtrl): control causing resize
            block_callback (bool): block move callbacks
        """
        super(CGStretchElem, self).resizeEvent(event=event)
        self.apply_stretch_update(ctrl=ctrl)

        if not block_callback and self.move_callback:
            self.move_callback(event=event, elem=self, ctrl=ctrl)
