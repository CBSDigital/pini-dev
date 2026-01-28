"""Tools for managing the work file object.

This is used to represent a work file in PiniHelper.
"""

import logging
import time

from pini import qt, icons
from pini.qt import QtGui
from pini.utils import strftime, cache_result, get_user

from .. import ph_utils

_LOGGER = logging.getLogger(__name__)

_BG_COL = qt.CColor('White')
_BG_COL.setAlphaF(0.1)
_BG_COL = qt.CColor('Transparent')

_DEF_TEXT_COL = qt.CColor('White')
_NO_OUTPUT_TEXT_COL = qt.CColor('Grey')
_NO_OUTPUT_TEXT_COL = _NO_OUTPUT_TEXT_COL.whiten(0.7)
_NEXT_TEXT_COL = qt.CColor('Chartreuse')

_NEXT_WORK_ICON = icons.find('Hatching')

_OUTPUT_ICONS = {
    'Cached': icons.find('Money Bag'),
    'Blasted': icons.find('Collision'),
    'Published': icons.find('Beer Mug'),
    'Rendered': icons.find('Film Frames'),
    'Empty': icons.find('White Circle'),
}


class PHWorkItem(qt.CListViewPixmapItem):  # pylint: disable=too-many-instance-attributes
    """Represents a work file in PiniHelper."""

    def __init__(self, list_view, helper, work):
        """Constructor.

        Args:
            list_view (QListView): work list
            helper (PiniHelper): parent dialog
            work (CPWork): work file to display
        """
        _LOGGER.debug('INIT PHWorkItem')
        _LOGGER.debug(' - WORK %s', work)

        self.work = work
        self.margin = 4
        self.helper = helper
        self.notes = ''

        if work is helper.next_work:
            self.notes = 'this will be created if you version up'
            _icon = _NEXT_WORK_ICON
            self.text_col = _NEXT_TEXT_COL
            self.output_tags = []
            self._mtime = time.time()
            self._has_thumb = False
        else:
            _icon = ph_utils.work_to_icon(work)
            self.output_tags = _get_output_tags(self.work)
            self.text_col = (
                _DEF_TEXT_COL if self.output_tags else _NO_OUTPUT_TEXT_COL)
            self._mtime = self.work.mtime()
            self._has_thumb = bool(self.work.obt_image())
            self.set_notes(self.work.notes, redraw=False)

        # Obtain icon
        if not isinstance(_icon, QtGui.QPixmap):
            _icon = ph_utils.obt_pixmap(_icon)
        assert isinstance(_icon, QtGui.QPixmap)
        self.icon = _icon

        super().__init__(
            list_view=list_view, col='Transparent', data=work,
            height=max(
                self.text_h, self.thumb_h + 20 if self._has_thumb else 0))

    @property
    def text_h(self):
        """Calculate height of text in this item.

        Returns:
            (float): height in pixels
        """
        return self.margin * 3 + self.line_h * self._to_n_lines()

    @property
    def thumb_h(self):
        """Calculate thumbnail height.

        Returns:
            (float): height in pixels
        """
        return self.metrics.size(0, '\n'.join('A' * 4)).height() * 1.1

    def _to_n_lines(self):
        """Calculate number of lines of text.

        Returns:
            (int): line count
        """
        _text = self._to_text()
        assert _text
        return 1 + _text.count('\n') + self.notes.count('\n')

    def _to_text(self):
        """Obtain display text (notes are not included).

        Returns:
            (str): text
        """
        if self.work is self.helper.next_work:
            _owner = get_user()
            _size_str = []
        else:
            _owner = self.work.owner()
            _size_str = self.work.nice_size()

        _date_s = strftime('%a %b %d %H:%M%P', self._mtime)
        _text = '\n'.join([
            f'v{self.work.ver} - {_date_s}',
            f' - Owner: {_owner}'])

        if _size_str:
            _text += '\n - Size: ' + _size_str
        if self.output_tags:
            _text += '\n - ' + '/'.join(self.output_tags)

        _text += '\n - Notes:'

        return _text

    def set_notes(self, notes, redraw=True):
        """Apply notes to this work file.

        Args:
            notes (str): notes to apply
            redraw (bool): redraw the element on update
        """
        _n_lines = self._to_n_lines()  # Read line count before update
        self.notes = notes or '-'
        self.notes = self.notes.replace('\\n', '\n')

        if redraw:

            self.redraw()

            # Handle size change
            if _n_lines != self._to_n_lines():
                _LOGGER.debug(' - LINE COUNT CHANGED')
                self.helper.flush_notes_stack()
                _work = self.list_view.selected_data()
                _scroll = self.list_view.verticalScrollBar()
                _pos = _scroll.sliderPosition()
                self.list_view.redraw()
                self.list_view.select_data(_work)
                _scroll.setSliderPosition(_pos)

    def draw_pixmap(self, pix):
        """Draw this element's pixmap.

        Args:
            pix (CPixmap): base pixmap to draw on
        """

        # Draw icon
        _icon_size = 35
        pix.draw_overlay(self.icon, pos=(8, 8), size=_icon_size)

        # Draw text
        _text = self._to_text()
        _text_pos = qt.to_p(_icon_size + 16.0, 4)
        pix.draw_text(
            _text, pos=_text_pos, col=self.text_col, font=self.font,
            line_h=self.line_h)

        # Draw notes
        _n_lines = _text.count('\n') + 1
        _n_offs_x = self.metrics.size(0, ' - Notes: ').width() + 1
        pix.draw_text(
            self.notes,
            pos=_text_pos + qt.to_p(
                _n_offs_x, (_n_lines - 1) * self.line_h + 0.5),
            col=self.text_col, font=self.font)

        # Draw output icons
        _keys = set(_OUTPUT_ICONS.keys())
        _keys.remove('Empty')
        _out_icons_offs_x = (
            self.metrics.size(0, 'A' * 25).width() + _text_pos.x())
        _out_icons_width = self.metrics.size(0, 'A' * 2).width()
        _out_icons_offs_y = self.metrics.size(0, 'A').height() / 2 + 6
        for _idx, _tag in enumerate(sorted(_keys, key=_sort_output_tag)):
            _icon_size = _out_icons_width
            if _tag not in self.output_tags:
                _tag = 'Empty'
                _icon_size *= 0.35
            _icon = _to_output_icon(_tag, size=_icon_size)
            _pos = (
                _out_icons_offs_x + (_out_icons_width * 1.3) * _idx,
                _out_icons_offs_y)
            pix.draw_overlay(_icon, pos=_pos, anchor='C')

        # Add thumb if available
        if self._has_thumb:
            _margin = 10
            _pix = ph_utils.obt_pixmap(self.work.image)
            _size = _pix.size() * self.thumb_h / _pix.height()  # pylint: disable=no-member
            self._draw_right_fade(pix, offset=_size.width() + _margin * 2)
            pix.draw_overlay(
                _pix, pos=(pix.width() - _margin, _margin),
                anchor='TR', size=_size)


def _get_output_tags(work):
    """Obtain output tags for the given work file.

    Args:
        work (CPWork): work file to read

    Returns:
        (str list): output tags (eg. ['Cached', 'Rendered'])
    """
    _o_tags = set()
    for _out in work.outputs:
        _LOGGER.debug(' - CHECKING OUT %s', _out)
        if (
                'blast' in _out.type_ or
                (_out.output_name and 'blast' in _out.output_name)):
            _o_tag = 'Blasted'
        elif _out.type_ == 'publish':
            _o_tag = 'Published'
        elif (
                _out.extn == 'abc' or
                _out.type_ in ('cache', 'cache_seq', 'ass_gz')):
            _o_tag = 'Cached'
        elif (
                _out.type_ in ('render', 'render_mov', 'mov') or
                _out.output_name == 'render'):
            _o_tag = 'Rendered'
        else:
            _LOGGER.debug('   - FAILED TO CLASSIFY %s', _out.type_)
            _o_tag = 'Outputs'
        _o_tags.add(_o_tag)

    if work.metadata.get('submitted'):
        _o_tags.add('Submitted')

    return sorted(_o_tags)


def _sort_output_tag(tag):
    """Sort function for output tag.

    Args:
        tag (str): output tag to sort

    Returns:
        (tuple): sort key
    """
    _order = ['Published', 'Blasted', 'Cached', 'Rendered']
    _idx = _order.index(tag) if tag in _order else len(_order)
    return _idx, tag


@cache_result
def _to_output_icon(tag, size=20):
    """Obtain icon for the given output tag.

    Args:
        tag (str): tag name (eg. Cached, Blasted)
        size (int): icon size

    Returns:
        (QPixmap): icon
    """
    _icon = _OUTPUT_ICONS[tag]
    return qt.CPixmap(_icon).resize(size)
