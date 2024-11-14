"""Tools for manging items in the scene references list."""

# pylint: disable=too-many-instance-attributes

from pini import qt, pipe
from pini.qt import QtGui
from pini.utils import basic_repr, Seq, Video

from ..ph_utils import output_to_icon, output_to_type_icon, obt_pixmap

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

        if highlight:
            self.bg_col = qt.CColor('White', alpha=0.1)
            self.text_col = 'White'
        else:
            self.text_col = 'LightGrey'
            self.bg_col = None

        self.icon = output_to_icon(self.output)

        super().__init__(
            list_view, col='Transparent', data=self.output)

    @property
    def info_font_size(self):
        """Calculate font size of info text.

        Returns:
            (float): font size
        """
        return self.font_size*0.9

    @property
    def info_y(self):
        """Calculate y-pos of info text.

        Returns:
            (float): y-pos
        """
        return self.font_size*5.5

    @property
    def label(self):
        """Obtain main label for this output element.

        Returns:
            (str): label
        """
        _out = self.output
        _ety_name = _out.asset or _out.shot

        # Handle restCache abcs
        if _out.extn == 'abc' and _out.output_name == 'restCache':
            return f'{_ety_name} ({_out.task} restCache)'

        # Handle shdCache ass.gz
        if _out.extn == 'gz' and _out.output_name == 'shdCache':
            return f'{_ety_name} ({_out.task} ass.gz)'

        _label = _out.output_name or _out.asset or _out.shot
        if isinstance(_out, (Seq, Video)):
            _label += ' '+_out.extn
        return _label

    @property
    def margin(self):
        """Calculate margin for this item.

        Returns:
            (float): margin in pixels
        """
        return self.font_size*0.3

    @property
    def sort_key(self):
        """Build sort key for this item to allow it to be compared with others.

        Returns:
            (tuple): sort key
        """
        return (self.label or '',
                self.output.tag or '',
                self.output.ver_n or '')

    @property
    def size_y(self):
        """Calculate height of this element.

        Returns:
            (int): height
        """
        _n_lines = 2.8 if not self.info else 4
        return _n_lines * self.line_h

    def draw_pixmap(self, pix):
        """Draw pixmap for this item.

        Args:
            pix (CPixmap): pixmap to draw on
        """
        super().draw_pixmap(pix)
        self.info = self.helper.ui.SInfo.isChecked()

        self.set_height(self.size_y)

        # Draw backdrop
        if self.bg_col:
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
        self._draw_right_fade(
            pix, offset=self.font_size * 7.5, width=self.font_size * 1)
        self._draw_right(pix)

    def _draw_left(self, pix):
        """Draw left side overlays.

        These will go underneath the right side in the case of any overlap.

        Args:
            pix (CPixmap): pixmap to draw on
        """
        _font = QtGui.QFont(self.font)
        _font.setBold(True)

        _left_m = self.font_size*3.9
        _icon_w = self.font_size*2.5
        _text_y = self.font_size*1.3

        # Draw icon
        if self.icon:
            _over = self.icon.resize(_icon_w)
            pix.draw_overlay(
                _over, pos=(self.font_size*0.8, pix.height()/2), anchor='L')

        # Draw asset text
        if not self.output.tag:
            _rect = pix.draw_text(
                self.label, pos=(_left_m, _text_y), col=self.text_col,
                font=_font)

        # Draw asset text with tag underneath
        else:
            _rect = pix.draw_text(
                self.label, pos=(_left_m, _text_y-5), col=self.text_col,
                font=_font)

            _font.setBold(False)
            _rect = pix.draw_text(
                self.output.tag,
                pos=(_left_m, self.line_h*1.4), col=self.text_col,
                font=_font)

        if self.info:
            _line_h = 43
            _font.setPointSize(self.info_font_size)
            pix.draw_text(
                self.output.strftime('%a %b %m %H:%M'),
                pos=(_left_m, self.info_y), col=self.text_col,
                font=_font, anchor='BL')

    def _draw_right(self, pix):
        """Draw right size overlays.

        Args:
            pix (CPixmap): pixmap to draw on
        """
        _font = QtGui.QFont(self.font)
        _font.setBold(True)

        _icon_w = self.font_size*2
        _right_m = pix.width() - self.font_size * 0.9
        _text_x = _right_m - self.font_size * 2.7
        _text_y = self.font_size*2.2

        _icon = output_to_type_icon(self.output)
        if _icon:
            _over = obt_pixmap(_icon, size=_icon_w)
            _pix = pix.draw_overlay(
                _over, pos=(_right_m+3, _text_y), anchor='R')

        # Draw version text
        if self.output.ver_n:
            _ver_text = f'v{self.output.ver}'
        else:
            _ver_n = pipe.CACHE.obt(self.output).find_latest().ver_n
            _ver_fmt = '* v{:03d}'
            _ver_text = _ver_fmt.format(_ver_n)
        _rect = pix.draw_text(
            _ver_text, pos=(_text_x, _text_y),
            col=self.text_col, anchor='R', font=_font)

        if self.info:
            _font = QtGui.QFont(self.font)
            _font.setPointSize(self.info_font_size)
            _font.setBold(False)
            pix.draw_text(
                self.output.owner(),
                pos=(_right_m, self.info_y), col=self.text_col,
                font=_font, anchor='BR')

    def __lt__(self, other):
        return self.sort_key < other.sort_key

    def __repr__(self):
        return basic_repr(self, self.output.entity.name)
