"""Tools for managing the CListViewPixmapItem."""

import logging
import os
import random

from pini.utils import basic_repr, fr_range

from ...q_mgr import QtGui
from . import qw_list_view_widget_item, qw_pixmap_label

_LOGGER = logging.getLogger(__name__)


class CListViewPixmapItem(qw_list_view_widget_item.CListViewWidgetItem):
    """This is CListView item which displays a pixmap.

    Internally this is managed using a CPixmapLabel widget.
    """

    _font = None

    def __init__(
            self, list_view, text=None, col=None, height=25, data=None,
            margin=4, draw_pixmap_func=None):
        """Constructor.

        Args:
            list_view (CListView): parent list view widget
            text (str): text to display
            col (QColor): base colour
            height (int): item height
            data (any): store item data
            margin (int): margin around image in pixels
            draw_pixmap_func (fn): override pixmap draw function
        """
        from pini import qt

        _widget = qw_pixmap_label.CPixmapLabel(
            text=text, margin=margin,
            draw_pixmap_func=draw_pixmap_func or self.draw_pixmap)
        self.text = text
        self.col = col or random.choice(qt.PASTEL_COLS)

        super().__init__(
            list_view=list_view, height=height, widget=_widget, data=data)

        self.redraw()

    @property
    def font(self):
        """Obtain default font for this item.

        Returns:
            (QFont): font
        """
        _size = int(os.environ.get('PINI_DEFAULT_FONT_SIZE', 7)) + 1
        if not self._font or not self._font.pointSize() == _size:
            self._font = QtGui.QFont()
            self._font.setPointSize(_size)
        return self._font

    @property
    def font_size(self):
        """Calculate default font size for this item.

        Returns:
            (int): font size
        """
        return self.font.pointSize()

    @property
    def line_h(self):
        """Calculate default line height for text in this item.

        Returns:
            (int): line height in pixels
        """
        return self.metrics.size(0, 'test').height()

    @property
    def metrics(self):
        """Obtain font metrics for this item.

        Returns:
            (QFontMetrics): metrics
        """
        return QtGui.QFontMetrics(self.font)

    def draw_pixmap(self, pix):
        """Draw this item's pixmap.

        Args:
            pix (QPixmap): pixmap to draw
        """
        self.widget.col = self.col
        self.widget.draw_pixmap(pix)

    def _draw_right_fade(self, pix, offset=50, width=10):
        """Draw gradient fade-off for left region overlapping right.

        Args:
            pix (CPixmap): pixmap to draw on
            offset (int): width of right section
            width (int): width of gradient
        """
        from pini import qt

        # Fill right section with transparent
        _col = qt.CColor('Transparent')
        _col.setAlphaF(0)
        pix.draw_rect(
            pos=(pix.width(), 0), size=(offset, pix.height()), col=_col,
            outline=None, anchor='TR', operation='Clear')

        # Draw grad
        _col = qt.CColor('White')
        for _idx, _fr in enumerate(fr_range(width)):
            _col.setAlphaF(_fr)
            pix.draw_rect(
                pos=(pix.width() - offset - _idx, 0),
                size=(1, pix.height()), col=_col,
                outline=None, anchor='TR', operation='DestinationIn')

    def redraw(self, size=None):
        """Redraw this item's pixmap.

        Args:
            size (QSize): override pixmap size

        Returns:
            (CPixmap): item pixmap
        """
        from pini import qt

        # Determine size
        _size_hint = size or qt.to_size(
            self.list_view.get_draw_width(), self.height)
        _LOGGER.debug('REDRAW %s %dx%d h=%d', self, _size_hint.width(),
                      _size_hint.height(), self.height)
        self.widget.resize(_size_hint)

        # Draw pixmap
        self.pixmap = self.widget.redraw()
        super().redraw(size=_size_hint)
        _LOGGER.debug(
            ' - REDRAW COMPLETE %dx%d widget_w=%d', _size_hint.width(),
            _size_hint.height(), self.widget.width())

        return self.pixmap

    def resizeEvent(self, event):
        """Triggered by resize.

        Passes list item size to the child widget and executes the
        widget redraw function to accomodate size changes.

        Args:
            event (QResizeEvent): triggered event
        """
        _LOGGER.debug('RESIZE %s', self)
        super().resizeEvent(event)
        self.redraw()

    def __repr__(self):
        return basic_repr(self, label=self.text)
