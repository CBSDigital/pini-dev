"""Tools for manging items in the scene references list."""

# pylint: disable=too-many-instance-attributes

from pini import qt
from pini.qt import QtGui
from pini.utils import basic_repr, Seq, Video

from ..ph_utils import output_to_icon, output_to_type_icon, obt_icon_pixmap

_FONT = QtGui.QFont()


class PHOutputItem(qt.CListViewPixmapItem):
    """Represents an output in the outputs list."""

    info = False

    def __init__(self, list_view, output, helper, highlight=True):
        """Constructor.

        Args:
            list_view (CListView): outputs list
            output (CPOutput): output to display
            helper (PiniHelper): pini helper
            highlight (bool): highlight this item
        """
        self.output = output
        self.helper = helper
        self.highlight = highlight

        self.margin = 3
        self.info_font_size = 5
        self.info_y = 31
        self.text_col = 'White' if highlight else 'Grey'
        self.text_y = 12

        self.bg_col = qt.CColor(self.text_col)
        self.bg_col.setAlphaF(0.2)

        self.icon = output_to_icon(self.output)
        self.icon_w = 16

        super(PHOutputItem, self).__init__(
            list_view, col='Transparent', data=self.output)

    @property
    def label(self):
        """Obtain main label for this output element.

        Returns:
            (str): label
        """
        _out = self.output

        # Handle restCache abcs
        if _out.extn == 'abc' and _out.output_name == 'restCache':
            return '{} ({} restCache)'.format(_out.entity.name, _out.task)

        # Handle shdCache ass.gz
        if _out.extn == 'gz' and _out.output_name == 'shdCache':
            return '{} ({} ass.gz)'.format(_out.entity.name,  _out.task)

        _label = _out.output_name or _out.entity.name
        if isinstance(_out, (Seq, Video)):
            _label += ' '+self.output.extn
        return _label

    @property
    def sort_key(self):
        """Build sort key for this item to allow it to be compared with others.

        Returns:
            (tuple): sort key
        """
        return (self.label or '',
                self.output.tag or '',
                self.output.ver_n or '')

    def draw_pixmap(self, pix):
        """Draw pixmap for this item.

        Args:
            pix (CPixmap): pixmap to draw on
        """
        super(PHOutputItem, self).draw_pixmap(pix)
        self.info = self.helper.ui.SInfo.isChecked()

        self.set_height(28 if not self.info else 36)

        # Draw backdrop
        pix.draw_rounded_rect(
            pos=(self.margin, self.margin/2),
            size=(pix.width()-self.margin*2, pix.height()-self.margin),
            outline=None, col=self.bg_col)

        # Add text/icon overlays
        _over = qt.CPixmap(pix.size())
        _over.fill('Transparent')
        self._draw_overlays(_over)
        pix.draw_overlay(_over)

    def _draw_overlays(self, pix):
        """Draw overlays (ie. text/icons) onto the given pixmap.

        This is to allow the overlaps to be drawn with a gradient
        fade-off between the left and right side, which is then
        overlaid onto the semi-transparent backdrop.

        Args:
            pix (CPixmap): pixmap to draw on
        """
        assert isinstance(pix, qt.CPixmap)
        self._draw_left(pix)
        self._draw_right_fade(pix, offset=44, width=12)
        self._draw_right(pix)

    def _draw_left(self, pix):
        """Draw left side overlays.

        These will go underneath the right side in the case of any overlap.

        Args:
            pix (CPixmap): pixmap to draw on
        """
        _left_m = 27

        # Draw icon
        _over = obt_icon_pixmap(self.icon, size=self.icon_w+4)
        pix.draw_overlay(
            _over, pos=(self.margin+1, self.text_y+1), anchor='L')

        # Draw asset text
        _FONT.setPointSize(7.5)
        _FONT.setBold(True)
        if not self.output.tag:
            _rect = pix.draw_text(
                self.label, pos=(_left_m, self.text_y), col=self.text_col,
                font=_FONT, anchor='L')
        else:
            _rect = pix.draw_text(
                self.label, pos=(_left_m, self.text_y-5), col=self.text_col,
                font=_FONT, anchor='L')
            _FONT.setPointSize(6.5)
            _FONT.setBold(False)
            _rect = pix.draw_text(
                self.output.tag,
                pos=(_left_m, self.text_y+5), col=self.text_col,
                font=_FONT, anchor='L')

        if self.info:
            _line_h = 43
            _FONT.setPointSize(self.info_font_size)
            pix.draw_text(
                self.output.strftime('%a %b %m %H:%M'),
                pos=(_left_m, self.info_y), col=self.text_col,
                font=_FONT, anchor='BL')

    def _draw_right(self, pix):
        """Draw right size overlays.

        Args:
            pix (CPixmap): pixmap to draw on
        """
        _right_m = pix.width() - self.margin*3

        _icon = output_to_type_icon(self.output)
        if _icon:
            _over = obt_icon_pixmap(_icon, size=self.icon_w)
            _pix = pix.draw_overlay(
                _over, pos=(_right_m+6, self.text_y+2), anchor='R')

        # Draw version text
        _text_x = _right_m - 13
        _FONT.setPointSize(7.5)
        _FONT.setBold(True)
        if self.output.ver_n:
            _ver_fmt = 'v{:03d}'
            _ver_n = self.output.ver_n
        else:
            _ver_n = self.output.find_latest().ver_n
            _ver_fmt = '* v{:03d}'
        _ver_text = _ver_fmt.format(_ver_n)
        _rect = pix.draw_text(
            _ver_text, pos=(_text_x, self.text_y),
            col=self.text_col, anchor='R', font=_FONT)

        if self.info:
            _FONT.setPointSize(self.info_font_size)
            _FONT.setBold(False)
            pix.draw_text(
                self.output.owner(),
                pos=(_right_m, self.info_y), col=self.text_col,
                font=_FONT, anchor='BR')

    def __lt__(self, other):
        return self.sort_key < other.sort_key

    def __repr__(self):
        return basic_repr(self, self.output.entity.name)
