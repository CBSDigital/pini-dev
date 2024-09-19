"""Tools for manging items in the scene references list."""

# pylint: disable=too-many-instance-attributes

from pini import qt, icons
from pini.qt import QtGui
from pini.utils import basic_repr, File

from ..ph_utils import (
    output_to_icon, UPDATE_ICON, output_to_type_icon, obt_pixmap)

_NEW_REF_ICON = icons.find('Star')
_DELETE_REF_ICON = icons.find('Cross Mark')
_MISSING_FROM_CACHE_ICON = icons.find('Adhesive Bandage')
_OUTDATED_REF_ICON = icons.find('Cloud')
_UNLOADED_REF_ICON = icons.find('Hollow Red Circle')


class PHSceneRefItem(qt.CListViewPixmapItem):
    """Represents a scene reference in the scene reference list."""

    info = False

    def __init__(self, list_view, ref, helper, status=None, output=None,
                 namespace=None):
        """Constructor.

        Args:
            list_view (CListView): scene refs list
            ref (CPipeRef): reference
            helper (PiniHelper): pini helper
            status (str): reference status (eg. new/update/delete)
            output (CPOutputBase): override output
            namespace (str): override namespace
        """
        self.ref = ref
        self.output = output or ref.output
        self.helper = helper
        self.status = status
        self.namespace = namespace or self.ref.namespace

        self.text_col = 'White'

        self.detail = self.over_icon = None

        # Get main icon
        _overlay = None
        if status == 'new':
            self.text_col = 'Gold'
            self.detail = 'new'
            _overlay = _NEW_REF_ICON
        elif status in ('update', 'rename'):
            self.text_col = 'GreenYellow'
            self.detail = 'update'
            _overlay = UPDATE_ICON
        elif status == 'delete':
            self.text_col = 'Red'
            self.detail = 'delete'
            _overlay = _DELETE_REF_ICON
        elif status == 'missing from cache':
            self.text_col = 'DarkGoldenrod'
            self.detail = 'missing from cache'
            _overlay = _MISSING_FROM_CACHE_ICON
        elif status is None:
            if not self.ref.is_loaded:
                self.text_col = 'Grey'
                self.detail = 'unloaded'
                _overlay = _UNLOADED_REF_ICON
            elif not self.ref.is_latest():
                self.text_col = 'LightPink'
                self.detail = 'outdated'
                _overlay = _OUTDATED_REF_ICON
        else:
            raise ValueError(status)

        self.bg_col = None
        if status or _overlay:
            self.bg_col = qt.CColor(self.text_col, alpha=0.2)
        if _overlay:
            _overlay = File(_overlay)
        self.icon = output_to_icon(self.output, overlay=_overlay)

        super(PHSceneRefItem, self).__init__(
            list_view, col='Transparent', data=self.ref)

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
    def margin(self):
        """Calculate margin for this item.

        Returns:
            (float): margin in pixels
        """
        return self.font_size*0.3

    @property
    def size_y(self):
        """Calculate height of this element.

        Returns:
            (int): height
        """
        _n_lines = 3.0 if not self.info else 4
        return _n_lines * self.line_h

    def draw_pixmap(self, pix):
        """Draw pixmap for this item.

        Args:
            pix (CPixmap): pixmap to draw on
        """
        super(PHSceneRefItem, self).draw_pixmap(pix)
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
        self._draw_left(pix)
        self._draw_right_fade(
            pix, offset=self.font_size * 8, width=self.font_size * 1)
        self._draw_right(pix)

    def _draw_left(self, pix):
        """Draw left side overlays.

        These will go underneath the right side in the case of any overlap.

        Args:
            pix (CPixmap): pixmap to draw on
        """
        _font = QtGui.QFont(self.font)
        _left_m = self.font_size*4.2
        _out = self.ref.to_output(use_cache=False)

        # Draw icon
        if self.icon:
            _over = self.icon.resize(self.font_size*2.5)
            pix.draw_overlay(
                _over, pos=(self.font_size*1, pix.height()/2), anchor='L')

        # Draw namespace
        _font.setBold(True)
        _rect = pix.draw_text(
            self.namespace,
            pos=(_left_m, self.font_size*0.8), col=self.text_col,
            font=_font)

        # Draw asset/tag
        _font.setBold(False)
        _label = _out.entity.name
        if _out.tag:
            _label += '/'+_out.tag
        pix.draw_text(
            _label,
            pos=(_left_m, self.font_size*2.4), col=self.text_col,
            font=_font, anchor='TL')

        if self.info and self.output:
            _line_h = self.font_size*4
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
        _right_m = pix.width() - self.margin*5
        _out = self.output or self.ref.to_output(use_cache=False)

        # Draw type icon
        _icon = output_to_type_icon(_out)
        if _icon:
            _over = obt_pixmap(_icon)
            pix.draw_overlay(
                _over, size=self.font_size*2,
                pos=(_right_m+3, self.font_size*2.3), anchor='R')

        # Draw version text
        _text_x = _right_m - self.font_size * 3.0
        _text_y = self.font_size * (1.7 if self.detail else 2.3)
        _font.setBold(True)
        if _out.ver_n:
            _ver_fmt = 'v{:03d}'
            _ver_n = _out.ver_n
        else:
            _ver_n = self.output.find_latest().ver_n
            _ver_fmt = '* v{:03d}'
        _ver_text = _ver_fmt.format(_ver_n)
        _rect = pix.draw_text(
            _ver_text, pos=(_text_x, _text_y),
            col=self.text_col, anchor='R', font=_font)

        # Draw detail
        if self.detail:
            _font.setPointSize(self.font_size*0.9)
            _font.setBold(False)
            _pos = (
                _right_m - self.font_size * 4.5,
                _text_y + self.font_size * 0.9)
            pix.draw_text(
                self.detail, pos=_pos,
                col=self.text_col, anchor='T', font=_font)

        if self.info:
            _font.setPointSize(self.info_font_size)
            _font.setBold(False)
            pix.draw_text(
                self.output.owner(),
                pos=(_right_m, self.info_y), col=self.text_col,
                font=_font, anchor='BR')

    def __repr__(self):
        return basic_repr(self, self.ref.namespace)
