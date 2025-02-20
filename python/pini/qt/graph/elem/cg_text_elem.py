"""Tools for managing text elements."""

import logging

from ... import q_utils, wrapper
from ...q_mgr import QtGui

from . import cg_move_elem

_LOGGER = logging.getLogger(__name__)


class CGTextElem(cg_move_elem.CGMoveElem):
    """An element displaying some text."""

    def __init__(
            self, text, parent, pos, size=None, text_size=10, lock=True,
            bg_col='Transparent', col='Black', space='graph', anchor='C',
            selectable=False, **kwargs):
        """Constructor.

        Args:
            text (str): text to display
            parent (CGraphElem/CGraphSpace): parent element
            pos (QPoint): element position
            size (QSize): element size
            text_size (int): text size (in graph space)
            lock (str): axis lock
                None/False - no lock
                H - horizontal lock
                V - vertical lock
                True - lock movement
            bg_col (str): background colour
            col (str): text colour
            space (str): space for pos/size (graph/fr)
            anchor (str): text anchor
            selectable (bool): whether this element is selectable
        """
        self.text = text

        _size = size
        _pos = q_utils.to_p(pos)
        if space == 'fr':
            _pos = parent.f2g(_pos)
            if _size:
                _size = parent.f2g(_size)
            _LOGGER.info(' - APPLIED FR SPACE %s %s', _pos, _size)
        if not _size:
            _font = QtGui.QFont()
            _font.setPointSize(text_size)
            _metrics = QtGui.QFontMetrics(_font)
            _size = _metrics.size(0, text) + q_utils.to_size(2)

        super().__init__(
            pos=_pos, size=_size, text_size=text_size, saveable=False,
            parent=parent, lock=lock, anchor=anchor, selectable=selectable,
            **kwargs)

        self.bg_col = q_utils.to_col(bg_col)
        self.col = q_utils.to_col(col)

    def update_pixmap(self, pix):
        """Update this element's pixmap.

        Args:
            pix (CPixmap): pixmap to draw on (in local space)
        """
        pix.fill(self.bg_col)
        _size = self.g2p(self.text_size_g)
        if self.anchor == 'B':
            _pos = q_utils.to_p(pix.width() / 2, pix.height())
        elif self.anchor == 'BL':
            _pos = q_utils.to_p(0, pix.height())
        elif self.anchor == 'C':
            _pos = pix.center()
        elif self.anchor == 'TL':
            _pos = wrapper.CPointF()
        else:
            raise NotImplementedError(self.anchor)
        pix.draw_text(
            self.text, anchor=self.anchor, pos=_pos, col=self.col,
            size=_size)
