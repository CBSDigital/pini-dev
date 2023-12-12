"""Tools for managing CTileWidgetItem."""

# pylint: disable=too-many-instance-attributes

import logging
import math

import six

from pini import dcc
from pini.utils import basic_repr, EMPTY, File

from . import qw_list_widget_item
from ...q_mgr import QtGui
from ...q_utils import to_size, to_icon, to_p

_LOGGER = logging.getLogger(__name__)


class CTileWidgetItem(qw_list_widget_item.CListWidgetItem):
    """Base class for a tile used in a CTileWidget."""

    _thumb_pix = None

    _filmstrip_pix = None
    _filmstrip_tile = None
    _filmstrip_tile_pix = None
    _filmstrip_scroll = None

    def __init__(
            self, name=None, col=None, size=100, label=EMPTY, margin=3,
            data=None, mouse_tracking=True, thumb=None, filmstrip=None):
        """Constructor.

        Args:
            name (str): name for tile
            col (str): base colour for tile
            size (QSize): tile size hint
            label (str): tile text
            margin (int): tile margin in pixels
            data (any): tile data
            mouse_tracking (bool): apply mouse tracking
            thumb (File): thumbnail image
            filmstrip (File): filmstrip image
        """
        super(CTileWidgetItem, self).__init__(data=data)

        self.name = name
        self.col = col
        self.label = label if label is not EMPTY else self.name
        self.mouse_tracking = mouse_tracking

        self.thumb = thumb
        self.filmstrip = filmstrip

        self.x_scroll = self.t_scroll = self.t_fr = None
        self.margin = margin

        self.set_size(size)

        self.redraw()

    @property
    def _base_pixmap(self):
        """Obtain base pixmap.

        If there is a filmstrip then a scrolled version of this is used.
        Otherwise, if there is a thumbnail then this is used. Otherwise
        nothing is returned.

        Returns:
            (CPixmap|None): base pixmap (if any)
        """
        from pini import qt
        _LOGGER.debug('BASE PIXMAP %s', self)

        _pix = None

        # Handle filmstrip
        if self.filmstrip and self.t_fr is not None:

            # Build strip pixmap
            if not self._filmstrip_pix:
                _LOGGER.debug(' - BUILDING FILMSTRIP %s', self.filmstrip)
                if isinstance(self._filmstrip_pix, (six.string_types, File)):
                    assert File(self._filmstrip_pix).exists()
                self._filmstrip_pix = qt.CPixmap(self.filmstrip)

            # Calculate strip scroll
            _strip_tile_h = self._filmstrip_pix.height()
            _strip_tile_w = _strip_tile_h
            _LOGGER.debug(
                ' - STRIP TILE SIZE %dx%d', _strip_tile_w, _strip_tile_h)
            _strip_tile_n = self._filmstrip_pix.width() / _strip_tile_w
            _strip_scroll = min(
                _strip_tile_n - 1,
                int(math.floor(self.t_fr * _strip_tile_n)))

            # Update strip by regenerating pixmap
            if _strip_scroll != self._filmstrip_scroll:
                _pix = qt.CPixmap(_strip_tile_w, _strip_tile_h)
                _pos = (-_strip_tile_w * _strip_scroll, 0)
                _pix.draw_overlay(self._filmstrip_pix, pos=_pos)
                self._filmstrip_scroll = _strip_scroll
                _pix = _pix.resize(self.tile_size)
                self._filmstrip_tile_pix = _pix
            else:
                _pix = self._filmstrip_tile_pix

        # Handle thumb
        if not _pix and self.thumb:
            if not self._thumb_pix:
                self._thumb_pix = qt.CPixmap(self.thumb)
                self._thumb_pix = self._thumb_pix.resize(self.tile_size)
            _pix = self._thumb_pix

        return _pix

    def set_size(self, size):
        """Set size hint for this tile.

        Args:
            size (QSize): size to apply
        """
        from pini import qt

        self.size = to_size(size)
        self.setSizeHint(self.size)

        # Set top left tile pos
        _offs_x, _offs_y = 0, 0
        if dcc.NAME == 'nuke':
            _offs_x, _offs_y = -2, 0
        self.tile_pos = to_p(
            self.margin + 1 + _offs_x,
            self.margin + 2 + _offs_y,
            class_=qt.CPoint)

        # Set tile size
        _offs_x, _offs_y = 0, 0
        if dcc.NAME == 'nuke':
            _offs_x, _offs_y = -2, 0
        self.tile_size = to_size(
            self.size.width() - self.tile_pos.x() - self.margin - 3 + _offs_x,
            self.size.height() - self.tile_pos.y() - self.margin - 2 + _offs_y)

    def set_x_scroll(self, x_scroll):
        """Set apply x scroll in pixels.

        This is used to faciliate animated thumbnails, and is applied to this
        tile as the mouse moves over it. The x-scroll is the number of pixels
        from the left the mouse postion is.

        The values for t-scroll (number of pixels across the tile) and t-fr
        (mouse position as fraction of tile width) are then calculated from
        this value.

        Args:
            x_scroll (int): pixels from the left
        """
        if not self.mouse_tracking:
            return

        self.x_scroll = x_scroll
        _t_scroll = x_scroll - self.margin
        self.t_scroll = max(0, min(_t_scroll, self.tile_size.width()))
        self.t_fr = 1.0 * self.t_scroll / self.tile_size.width()
        _LOGGER.debug('SET SCROLL %s %d %.02f', self, self.t_scroll, self.t_fr)

        self.redraw()

    def _draw_pixmap(self):
        """Draw pixmap for this tile.

        This can be re-implemented in a sub-class to customise the pixmap.

        Returns:
            (CPixmap): pixmap to display in tile
        """
        from pini import qt

        _base_pix = qt.CPixmap(self.size)
        _base_pix.fill('Transparent')

        # Build tile pixmap
        _tile_pix = qt.CPixmap(self.tile_size)
        self.update_pixmap(_tile_pix)

        # Draw tile pixmap as rounded rectangle
        _tfm = QtGui.QTransform()
        _tfm.translate(*self.tile_pos.to_tuple())
        _brush = QtGui.QBrush(_tile_pix)
        _brush.setTransform(_tfm)
        _base_pix.draw_rounded_rect(
            pos=self.tile_pos, size=self.tile_size, brush=_brush, outline=None)

        return _base_pix

    def update_pixmap(self, pix, text=True):
        """Update this tile's pixmap.

        The pixmap is drawn in a rounded rectangle inside the tile margins.

        Args:
            pix (CPixmap): pixmap to draw on
            text (bool): draw text
        """
        from pini import qt
        _LOGGER.debug('UPDATE PIXMAP %s', self._base_pixmap)

        # Fix base
        if self._base_pixmap:
            pix.fill('Transparent')
            pix.draw_overlay(self._base_pixmap)
        else:
            pix.fill(self.col or 'Red')

        if text:

            # Draw tile text
            if self.label:
                _pos = pix.center() + qt.to_p(0, 1)
                pix.draw_text(self.label, pos=_pos, anchor='C', size=10)

            # Draw thumb scroll fraction as percentage
            if self.t_fr is not None:
                _text = '{:.00f}%'.format(self.t_fr * 100)
                _pos = qt.to_p(pix.center().x(), pix.height() - 3)
                pix.draw_text(_text, pos=_pos, anchor='B', size=8)

    def redraw(self):
        """Update icon this tile's icon."""
        _pix = self._draw_pixmap()
        self.setIcon(to_icon(_pix))

    def __repr__(self):
        return basic_repr(self, self.name)
