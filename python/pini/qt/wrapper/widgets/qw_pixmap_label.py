"""Tools for managing the CPixmapLabel widget."""

import logging
import time

from pini.utils import basic_repr, str_to_seed

from ...q_mgr import QtWidgets, Qt

_LOGGER = logging.getLogger(__name__)


class CPixmapLabel(QtWidgets.QLabel):
    """A QLabel which displays a pixmap."""

    def __init__(
            self, parent=None, text=None, col=None, margin=4,
            draw_pixmap_func=None):
        """Constructor.

        Args:
            parent (QWidget): parent widget (passed by designer on build ui)
            text (str): text to display in pixmap
            col (str): base colour for pixmap
            margin (int): margin size in pixels
            draw_pixmap_func (fn): override draw pixmap function
        """
        from pini import qt
        assert parent is None or isinstance(parent, QtWidgets.QWidget)

        super().__init__(parent=parent)

        _rand = str_to_seed(self.objectName())
        self.col = col or _rand.choice(qt.PASTEL_COLS)
        self.text = text  # Hidden to avoid clash with text method
        self.margin = margin
        self.draw_pixmap_func = draw_pixmap_func
        self.update_t = None

        self.setAlignment(Qt.AlignCenter)
        self.setMinimumSize(1, 1)

    def draw_pixmap(self, pix):
        """Draw this widget's pixmap.

        By default the pixmap is filled with a margined rectangle using the
        base colour, and any text is applied in the widget centre. This
        can be reimplemented in a subclass to draw more complex pixmaps.

        Args:
            pix (QPixmap): pixmap to draw on
        """
        from pini import qt

        if self.margin:
            _size = pix.size() - qt.to_size(self.margin * 2, self.margin * 2)
        else:
            _size = pix.size()
        pix.draw_rect(col=self.col, pos=(self.margin, self.margin),
                      size=_size, outline=None)
        if self.text:
            _LOGGER.debug('TEXT %s', self.text)
            assert isinstance(self.text, str)
            pix.draw_text(self.text, pos=pix.center(), anchor='C')

    def redraw(self):
        """Redraw this widget.

        This is triggered by a resize of the parent widget.

        Returns:
            (CPixmap): item pixmap
        """
        _LOGGER.debug('REDRAW %s', self)
        from pini import qt

        _size = self.size()
        _pix = qt.CPixmap(_size)
        _pix.fill('Transparent')
        _draw_pixmap_func = self.draw_pixmap_func or self.draw_pixmap
        _draw_pixmap_func(_pix)
        self.setPixmap(_pix)
        self.update_t = time.time()
        return _pix

    def resizeEvent(self, event):
        """Triggered by resize.

        Args:
            event (QResizeEvent): triggered event
        """
        _LOGGER.debug('RESIZE %s', self)
        super().resizeEvent(event)
        self.redraw()

    def __repr__(self):
        return basic_repr(self, label=self.text)
