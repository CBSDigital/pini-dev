"""Tools for manging items in the scene references list."""

# pylint: disable=too-many-instance-attributes

from pini import qt, icons
from pini.qt import QtGui
from pini.utils import basic_repr, File

from ..ph_utils import (
    output_to_icon, UPDATE_ICON, output_to_type_icon, obt_icon_pixmap)

_NEW_REF_ICON = icons.find('Star')
_DELETE_REF_ICON = icons.find('Cross Mark')
_MISSING_FROM_CACHE_ICON = icons.find('Adhesive Bandage')
_OUTDATED_REF_ICON = icons.find('Cloud')
_UNLOADED_REF_ICON = icons.find('Hollow Red Circle')

_FONT = QtGui.QFont()


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

        self.margin = 3
        self.info_font_size = 5
        self.info_y = 35
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

        self.bg_col = qt.CColor(self.text_col)
        self.bg_col.setAlphaF(0.2)
        if _overlay:
            _overlay = File(_overlay)
        self.icon = output_to_icon(self.output, overlay=_overlay)

        super(PHSceneRefItem, self).__init__(
            list_view, col='Transparent', data=self.ref)

    def draw_pixmap(self, pix):
        """Draw pixmap for this item.

        Args:
            pix (CPixmap): pixmap to draw on
        """
        super(PHSceneRefItem, self).draw_pixmap(pix)
        self.info = self.helper.ui.SInfo.isChecked()

        self.set_height(40 if self.info else 32)

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
        self._draw_left(pix)
        self._draw_right_fade(pix, offset=49, width=12)
        self._draw_right(pix)

    def _draw_left(self, pix):
        """Draw left side overlays.

        These will go underneath the right side in the case of any overlap.

        Args:
            pix (CPixmap): pixmap to draw on
        """
        _left_m = 30
        _out = self.ref.to_output(cache=False)

        # Draw icon
        _over = obt_icon_pixmap(self.icon, size=25)
        pix.draw_overlay(_over, (self.margin, self.margin+12), anchor='L')

        # Draw namespace
        _FONT.setPointSize(7.5)
        _FONT.setBold(True)
        _rect = pix.draw_text(
            self.namespace,
            pos=(_left_m, 10), col=self.text_col,
            font=_FONT, anchor='L')

        # Draw asset/tag
        _FONT.setPointSize(6.5)
        _FONT.setBold(False)
        _label = _out.entity.name
        if _out.tag:
            _label += '/'+_out.tag
        pix.draw_text(
            _label,
            pos=(_left_m, _rect.bottom()-5), col=self.text_col,
            font=_FONT, anchor='TL')

        if self.info and self.output:
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
        _out = self.output or self.ref.to_output(cache=False)

        # Draw type icon
        _icon = output_to_type_icon(_out)
        if _icon:
            _over = obt_icon_pixmap(_icon, size=16)
            pix.draw_overlay(_over, (_right_m+6, 16), anchor='R')

        # Draw version text
        _text_x = _right_m - 13
        _text_y = 12 if self.detail else 14
        _FONT.setPointSize(7.5)
        _FONT.setBold(True)
        if _out.ver_n:
            _ver_fmt = 'v{:03d}'
            _ver_n = _out.ver_n
        else:
            _ver_n = self.output.find_latest().ver_n
            _ver_fmt = '* v{:03d}'
        _ver_text = _ver_fmt.format(_ver_n)
        _rect = pix.draw_text(
            _ver_text, pos=(_text_x, _text_y),
            col=self.text_col, anchor='R', font=_FONT)

        # Draw detail
        if self.detail:
            _FONT.setPointSize(4.5)
            _FONT.setBold(False)
            _pos = qt.to_p(_text_x-9, _text_y+5)
            # print self.detail, _rect, _pos
            pix.draw_text(
                self.detail, pos=_pos,
                col=self.text_col, anchor='T', font=_FONT)

        if self.info:
            _FONT.setPointSize(self.info_font_size)
            _FONT.setBold(False)
            pix.draw_text(
                self.output.owner(),
                pos=(_right_m, self.info_y), col=self.text_col,
                font=_FONT, anchor='BR')

    def __repr__(self):
        return basic_repr(self, self.ref.namespace)
