"""Tools for managing the work file object

This is used to represent a work file in PiniHelper.
"""

import logging
import time

from pini import qt, icons, dcc
from pini.qt import QtGui
from pini.utils import strftime, cache_result, get_user

from .. import ph_utils

_LOGGER = logging.getLogger(__name__)

# Setup font/metrics
_FONT = QtGui.QFont()
_LOGGER.info(
    ' - FONT %s %s %s', _FONT, _FONT.pointSize(),
    qt.get_application().font().pointSize())
_OUTPUT_ICONS_OFFS_X = 195
_NOTES_OFFS_X = 47
_THUMB_H = 53
if qt.CListView.DEFAULT_FONT_SIZE is not None:
    if qt.CListView.DEFAULT_FONT_SIZE != 8:
        raise NotImplementedError(qt.CListView.DEFAULT_FONT_SIZE)
    _FONT.setPointSize(8)
    _NOTES_OFFS_X -= 5
    _THUMB_H += 5
    _LOGGER.info(' - APPLYING DCC FONT %s', dcc.NAME)
_METRICS = QtGui.QFontMetrics(_FONT)

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

        # Causes seg fault if declared globally
        self._line_h = _METRICS.size(0, 'test').height()

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
        self.icon = ph_utils.obt_pixmap(_icon)

        _text_h = 9 + self._line_h * self._to_n_lines()

        super(PHWorkItem, self).__init__(
            list_view=list_view, col='Transparent', data=work,
            height=max(_text_h, _THUMB_H+20 if self._has_thumb else 0))

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

        _text = '\n'.join([
            'v{work.ver} - {date}',
            ' - Owner: {owner}',
        ]).format(
            work=self.work,
            owner=_owner,
            date=strftime('%a %b %d %H:%M%P', self._mtime))

        if _size_str:
            _text += '\n - Size: '+_size_str
        if self.output_tags:
            _text += '\n - '+'/'.join(self.output_tags)

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
        pix.draw_overlay(
            self.icon, pos=(8, pix.height()/2), anchor='L',
            size=_icon_size)

        # Draw text
        _text = self._to_text()
        _pos = qt.to_p(_icon_size+16, 4)
        pix.draw_text(
            _text, pos=_pos, col=self.text_col, font=_FONT)
        _n_lines = _text.count('\n') + 1
        pix.draw_text(
            self.notes,
            pos=_pos + qt.to_p(_NOTES_OFFS_X, (_n_lines-1)*self._line_h),
            col=self.text_col, font=_FONT)

        # Draw output tags
        _keys = set(_OUTPUT_ICONS.keys())
        _keys.remove('Empty')
        for _idx, _tag in enumerate(sorted(_keys, key=_sort_output_tag)):
            if _tag not in self.output_tags:
                _tag = 'Empty'
                _size = 3
            else:
                _size = 13
            _icon = _to_output_icon(_tag, size=_size)
            _indent = 11
            _pos = (_indent + _OUTPUT_ICONS_OFFS_X + 13*_idx, _indent)
            pix.draw_overlay(_icon, pos=_pos, anchor='C')

        # Add thumb if available
        if self._has_thumb:
            _margin = 10
            _pix = ph_utils.obt_pixmap(self.work.image)
            _size = _pix.size() * _THUMB_H/_pix.height()  # pylint: disable=no-member
            self._draw_right_fade(pix, offset=_size.width()+_margin*2)
            pix.draw_overlay(
                _pix, pos=(pix.width()-_margin, _margin),
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
