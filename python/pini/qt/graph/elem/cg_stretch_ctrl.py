"""Tools for managing stretch controls, used to control stretch element."""

import logging

from ... import wrapper
from . import cg_move_elem

_LOGGER = logging.getLogger(__name__)


class CGStretchCtrl(cg_move_elem.CGMoveElem):
    """Control for a stretch element."""

    def __init__(self, stretch, limit, **kwargs):
        """Constructor.

        Args:
            stretch (CGStretchElem): parent stretch element
            limit (str): how to limit movement
        """
        super().__init__(
            saveable=False, selectable=False, **kwargs)
        self.stretch = stretch
        self.limit = limit

    def _to_limit_min(self):
        """Calculate movement limit minimum.

        Returns:
            (CPointF): minimum position
        """
        if self.limit == 'x_min':
            return wrapper.CPointF(
                self.stretch.rect_g.left() + self.stretch.ctrl_w,
                self.stretch.rect_g.top())
        if self.limit == 'y_min':
            return wrapper.CPointF(
                self.stretch.rect_g.left(),
                self.stretch.rect_g.top() + self.stretch.ctrl_w)
        return None

    def _to_limit_max(self):
        """Calculate movement limit maximum.

        Returns:
            (CPointF): maximum position
        """
        if self.limit == 'x_max':
            return wrapper.CPointF(
                self.stretch.rect_g.right() - self.stretch.ctrl_w,
                self.stretch.rect_g.bottom())
        if self.limit == 'y_max':
            return wrapper.CPointF(
                self.stretch.rect_g.right(),
                self.stretch.rect_g.bottom() - self.stretch.ctrl_w)
        return None

    def mousePressEvent(self, event=None):
        """Triggered by mouse press.

        Args:
            event (QMouseEvent): triggered event
        """
        _LOGGER.debug('MOUSE PRESS %s', self)
        _min = self._to_limit_min() or self.stretch.local_pos_g_min
        _max = self._to_limit_max() or self.stretch.local_pos_g_max
        self.set_move_limits(min_=_min, max_=_max)
        _event = super().mousePressEvent(event)
        return _event

    def mouseMoveEvent(self, event=None):
        """Triggered by mouse move.

        Args:
            event (QMouseEvent): triggered event
        """
        _event = super().mouseMoveEvent(event)
        self.stretch.resizeEvent(ctrl=self)
        _LOGGER.debug(' - MOUSE MOVE %s %s', self, self.local_pos_g)
        return _event

    def mouseReleaseEvent(self, event=None, update_selection=True):  # pylint: disable=unused-argument
        """Triggered by mouse release.

        Args:
            event (QMouseEvent): triggered event
            update_selection (bool): N/A (ineffective)
        """
        _event = super().mouseReleaseEvent(event)
        self.stretch.mouseReleaseEvent(event, update_selection=False)
        return _event
