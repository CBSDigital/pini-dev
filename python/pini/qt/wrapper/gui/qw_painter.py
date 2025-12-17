"""Tools for adding functionality to QPixmap."""

import logging
import math

from ...q_mgr import QtGui, Qt, QtCore

_LOGGER = logging.getLogger(__name__)


class CPainter(QtGui.QPainter):
    """Wrapper for QPainter."""

    def apply_rotate(self, rotate, rect, anchor):
        """Apply rotation.

        Args:
            rotate (float): angle (in degrees)
            rect (QRect): guide region
            anchor (str): draw anchor

        Returns:
            (QRect): draw region after rotation applied
        """
        from pini import qt

        if anchor == 'C':
            _pos = qt.CPointF(rect.center())
        elif anchor == 'L':
            _pos = qt.CPointF(rect.left(), rect.center().y())
        elif anchor == 'R':
            _pos = qt.CPointF(rect.right(), rect.center().y())
        elif anchor == 'T':
            _pos = qt.CPointF(rect.center().x(), rect.top())
        elif anchor == 'TL':
            _pos = qt.CPointF(rect.topLeft())
        elif anchor == 'TR':
            _pos = qt.CPointF(rect.topRight())
        else:
            raise ValueError(anchor)
        _pos += qt.CPointF(1, 1)

        # Calculate offset
        _len = _pos.length()
        _bearing = _pos.bearing()
        _bearing_dash = _bearing - rotate
        _pos_dash = qt.CPointF(
            round(_len * math.cos(math.radians(_bearing_dash))),
            round(_len * math.sin(math.radians(_bearing_dash))))
        _offs = _pos_dash - _pos

        # Apply rotation
        self.rotate(rotate)
        _rect = qt.to_rect(_offs + qt.to_p(0, 1) + rect.topLeft(),
                           qt.to_size(rect.width(), rect.height() - 1))

        return _rect

    def draw_text(
            self, text, pos=(0, 0), anchor='TL', col='white', font=None,
            size=None, line_h=None, rotate=0.0, rect=None, align=None):
        """Draw text using this paint device.

        Args:
            text (str): text to draw
            pos (QPoint): draw position
            anchor (str): anchor position
            col (QColor): text colour
            font (QFont): override font
            size (int): override text size
            line_h (int): text newline separation in pixels
            rotate (float): apply rotation (in degrees)
            rect (QRect): apply wrapped text in rectangle
                (overrides pos arg)
            align (AlignmentFlag): override alignment flag
        """
        _kwargs = locals()
        from pini import qt

        # Check args
        if not isinstance(text, str):
            raise TypeError(f"Bad text type {text} ({type(text).__name__})")
        if size is not None and not int(size):
            return None

        # Add by line if line height declared
        if line_h is not None and '\n' in text:
            assert not rect
            del _kwargs['self']
            del _kwargs['rect']
            self._draw_text_lines(**_kwargs)
            return None

        _LOGGER.debug("Adding text %s", text)
        _pos = qt.to_p(pos)
        if rect:
            _rect = rect
            _align = Qt.AlignLeft | Qt.TextWordWrap
        else:
            _align, _rect = self._draw_text_get_rect(pos=_pos, anchor=anchor)
        if align:
            _align = align

        # Setup font
        _font = qt.to_font(font)
        if size:
            _font.setPointSizeF(size)
        self.setFont(_font)

        # Apply rotation
        if rotate:
            _rect = self.apply_rotate(rotate=rotate, rect=_rect, anchor=anchor)

        # Draw text
        _col = qt.to_col(col or 'White')
        self.setPen(_col)
        self.drawText(_rect, _align, text)

        return _rect

    def _draw_text_get_rect(self, pos, anchor):
        """Get draw text rect.

        Args:
            pos (QPoint): text position
            anchor (str): text anchor

        Returns:
            (str): text draw region
        """
        _x, _y = pos.x(), pos.y()
        _w, _h = self.window().width(), self.window().height()

        if anchor == 'BL':
            _rect = QtCore.QRect(_x, 0, _w - _x + 1, _y + 1)
            _align = Qt.AlignLeft | Qt.AlignBottom
        elif anchor == 'BR':
            _rect = QtCore.QRect(0, 0, _x + 1, _y + 1)
            _align = Qt.AlignRight | Qt.AlignBottom
        elif anchor == 'B':
            _rect = QtCore.QRect(0, 0, 2 * _x + 1, _y + 1)
            _align = Qt.AlignHCenter | Qt.AlignBottom
        elif anchor == 'C':
            _rect = QtCore.QRect(0, 0, 2 * _x + 1, 2 * _y + 1)
            _align = Qt.AlignHCenter | Qt.AlignVCenter
        elif anchor == 'L':
            _rect = QtCore.QRect(_x, 0, _w + 1, 2 * _y + 1)
            _align = Qt.AlignVCenter | Qt.AlignLeft
        elif anchor == 'R':
            _rect = QtCore.QRect(0, 0, _x + 1, 2 * _y + 1)
            _align = Qt.AlignRight | Qt.AlignVCenter
        elif anchor in ('T', 'TC'):
            _rect = QtCore.QRect(0, _y, 2 * _x + 1, _h + 1)
            _align = Qt.AlignHCenter | Qt.AlignTop
        elif anchor == 'TL':
            _rect = QtCore.QRect(_x, _y, _w + 1, _h + 1)
            _align = Qt.AlignLeft | Qt.AlignTop
        elif anchor == 'TR':
            _rect = QtCore.QRect(0, _y, _x + 1, _h - _y + 1)
            _align = Qt.AlignRight | Qt.AlignTop
        else:
            raise ValueError(f'Unhandled anchor: {anchor}')

        return _align, _rect

    def _draw_text_lines(  # pylint: disable=unused-argument
            self, text, line_h, pos=(0, 0), anchor='TL', col='White',
            font=None, size=None, rotate=0.0, align=None):
        """Draw text line by line.

        This allows control over line separation

        Args:
            text (str): text to draw
            line_h (int): line height in pixels
            pos (QPoint): text position
            anchor (str): text anchor
            col (QColor): text colour
            font (QFont): text font
            size (int): text point size
            rotate (float): text rotation
            align (AlignmentFlag): override alignment flag
        """
        _kwargs = locals()
        del _kwargs['self']
        del _kwargs['line_h']
        from pini import qt

        if rotate or align:
            raise NotImplementedError

        _lines = text.split('\n')
        if anchor.startswith('B'):
            _lines.reverse()
        for _idx, _line in enumerate(_lines):

            # Set offset
            _offs = _idx * line_h
            if anchor.startswith('B'):
                _offs *= -1
            elif anchor in 'LCR':
                _offs -= 0.5 * line_h * (len(_lines) - 1)

            # Draw line
            _kwargs['pos'] = qt.to_p(pos) + qt.Y_AXIS * _offs
            _kwargs['text'] = _line
            self.draw_text(**_kwargs)
