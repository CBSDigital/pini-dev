"""Tools for managing the graph window.

This is a window containing just a graph space.
"""

import logging

from pini.utils import File

from .. import custom, q_utils

_LOGGER = logging.getLogger(__name__)

_DIR = File(__file__).to_dir()
_UI_FILE = _DIR.to_file('space_window.ui')


class CGraphWindow(custom.CUiMainWindow):
    """A window containing a single graph space widget."""

    def __init__(
            self, fps=None, title='Space Window', load_settings=True,
            settings_file=None):
        """Constructor.

        Args:
            fps (float): frame rate
            title (str): window title
            load_settings (bool): load graph settings
            settings_file (str): override path to graph settings file
        """
        super().__init__(
            ui_file=_UI_FILE, title=title, fps=fps)
        if settings_file:
            self.ui.Graph.set_settings_file(settings_file)
        if load_settings:
            self.ui.Graph.load_settings()
        else:
            self.ui.Graph.frame_elems()

    def init_ui(self, bg_col='BottleGreen', legend=''):
        """Build ui elements.

        Args:
            bg_col (str): override space background colour
            legend (str): override space legend
        """
        self.ui.Graph.set_window(self)
        self.ui.Graph.setup_shortcuts()

        # Setup space
        self.ui.Graph.col = bg_col
        self.ui.Graph.legend = legend
        self.ui.Graph.add_draw_callback(self.update_pixmap)

    def g2p(self, item):
        """Convert object from graph space to pixmap space.

        Args:
            item (CPointF|CRectF|CSizeF): object to convert

        Returns:
            (CPointF|CRectF|CSizeF): converted object
        """
        return self.ui.Graph.g2p(item)

    def p2g(self, item):
        """Convert object from pixmap space to graph space.

        Args:
            item (CPointF|CRectF|CSizeF): object to convert

        Returns:
            (CPointF|CRectF|CSizeF): converted object
        """
        return self.ui.Graph.p2g(item)

    def update_pixmap(self, pix):
        """Called on draw space.

        Args:
            pix (CPixmap): space pixmap to draw on
        """
        _LOGGER.debug('DRAW SPACE %s %s', self, pix)

    def _draw_text(self, pix, text, pos, anchor='TL', size=None):
        """Draw text given text in this window's space.

        Args:
            pix (CPixmap): space pixmap to draw on
            text (str): text to draw
            pos (QPointF): draw position (in graph space)
            anchor (str): text anchor
            size (float): override text size (in graph space)
        """
        pix.draw_text(
            text, anchor=anchor, pos=self.ui.Graph.g2p(pos),
            size=self.ui.Graph.g2p(size or self.text_size))

    def closeEvent(self, event=None):
        """Triggered by closing window.

        Args:
            event (QCloseEvent): close event
        """
        _LOGGER.info(' - CLOSE %s', self)
        self.ui.Graph.save_settings()
        super().closeEvent(event)

    @q_utils.safe_timer_event
    def timerEvent(self, event):
        """Triggered by timer.

        Args:
            event (QTimerEvent): triggered event
        """
        self.ui.Graph.redraw()
