"""Tools for managing the basic move element."""

# pylint: disable=too-many-instance-attributes

import logging

from ... import q_utils, wrapper
from . import cg_pixmap_elem

_LOGGER = logging.getLogger(__name__)


class CGMoveElem(cg_pixmap_elem.CGPixmapElem):
    """An element which can be moved in 2D space."""

    anchor_g = None

    local_pos_g_min = None
    local_pos_g_max = None

    def __init__(
            self, lock=None, saveable=None, selectable=True, move_callback=None,
            **kwargs):
        """Constructor.

        Args:
            lock (str): axis lock
                None/False - no lock
                H - horizontal lock
                V - vertical lock
                True - lock movement
            saveable (bool): whether element settings are saveable
            selectable (bool): whether this element is selectable
            move_callback (fn): function to execute on move
        """
        self.lock = lock
        self.move_callback = move_callback

        _saveable = saveable
        if _saveable is None:
            _saveable = lock is not True
        super(CGMoveElem, self).__init__(
            draggable=True, saveable=_saveable, selectable=selectable, **kwargs)

        self.local_pos_g_default = self.local_pos_g
        self.size_g_default = self.size_g

    def get_settings(self):
        """Read settings for this element.

        Returns:
            (dict): saveable settings
        """
        _settings = super(CGMoveElem, self).get_settings()

        # Get pos
        _pos = list(self.local_pos_g.to_tuple())
        if self.lock == 'V':
            _pos[1] = None
        elif self.lock == 'H':
            _pos[0] = None
        elif self.lock is True:
            _pos = None
        elif self.lock is False:
            pass
        else:
            raise NotImplementedError(self.lock)
        _settings['pos'] = _pos

        return _settings

    def reset(self):
        """Reset this element."""
        self.local_pos_g = self.local_pos_g_default
        _LOGGER.info(' - RESET LOCAL POS G %s', self.local_pos_g)
        super(CGMoveElem, self).reset()

    def set_move_limits(self, min_=None, max_=None):
        """Set movement limits for this control.

        Args:
            min_ (QPointF): minimum position
            max_ (QPointF): maximum position
        """
        self.local_pos_g_min = min_
        self.local_pos_g_max = max_

    def mousePressEvent(self, event=None):  # pylint: disable=useless-return
        """Triggered by mouse press.

        The function returns None, meaning that the event is not passed to
        elements underneath this one.

        Args:
            event (QMouseEvent): triggered event
        """
        _event = super(CGMoveElem, self).mousePressEvent(event)
        if not self.enabled:
            return _event
        if self.lock is True:
            return _event
        self.anchor_g = self.local_pos_g
        return None

    def _apply_min_limit(self, pos):
        """Apply min move limit.

        Args:
            pos (CPointF): point to crop

        Returns:
            (CPointF): point with limit applied
        """
        if self.anchor == 'BL':
            _min = self.local_pos_g_min + q_utils.to_p(0, self.size_g.height())
        elif self.anchor == 'C':
            _min = self.local_pos_g_min + q_utils.to_p(self.size_g/2)
        elif self.anchor == 'TL':
            _min = self.local_pos_g_min
        elif self.anchor == 'TR':
            _min = self.local_pos_g_min + q_utils.to_p(self.size_g.width(), 0)
        else:
            raise NotImplementedError(self.anchor)
        _LOGGER.debug(' - APPLYING MIN')

        return wrapper.CPointF(max(pos.x(), _min.x()), max(pos.y(), _min.y()))

    def _apply_max_limit(self, pos):
        """Apply max move limit.

        Args:
            pos (CPointF): point to crop

        Returns:
            (CPointF): point with limit applied
        """
        if self.anchor == 'BL':
            _max = self.local_pos_g_max - q_utils.to_p(self.size_g.width(), 0)
        elif self.anchor == 'C':
            _max = self.local_pos_g_max - q_utils.to_p(self.size_g/2)
        elif self.anchor == 'TL':
            _max = self.local_pos_g_max - q_utils.to_p(self.size_g)
        elif self.anchor == 'TR':
            _max = self.local_pos_g_max - q_utils.to_p(0, self.size_g.height())
        else:
            raise NotImplementedError(self.anchor)

        return wrapper.CPointF(min(pos.x(), _max.x()), min(pos.y(), _max.y()))

    def mouseMoveEvent(self, event=None):
        """Triggered by mouse move.

        Args:
            event (QMouseEvent): triggered event
        """
        _event = super(CGMoveElem, self).mouseMoveEvent(event)

        if self.lock is True:
            return _event

        _LOGGER.debug('MOUSE MOVE')

        # Calculate drag vector
        if not self.drag_vect_g:
            _drag_v = wrapper.CPointF()
        elif not self.lock:
            _drag_v = self.drag_vect_g
        elif self.lock == 'H':
            _drag_v = wrapper.CPointF(0, self.drag_vect_g.y())
        elif self.lock == 'V':
            _drag_v = wrapper.CPointF(self.drag_vect_g.x(), 0)
        else:
            raise ValueError(self.lock)
        _pos = self.anchor_g + _drag_v

        # Apply min/max position limits
        if self.local_pos_g_min:
            _pos = self._apply_min_limit(_pos)
        if self.local_pos_g_max:
            _pos = self._apply_max_limit(_pos)
        self.local_pos_g = _pos

        if self.move_callback:
            self.move_callback(event=event, elem=self)

        return _event
