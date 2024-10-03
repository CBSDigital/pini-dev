"""Tools for managing the progress dialog."""

# pylint: disable=too-many-instance-attributes,no-member

import collections
import copy
import functools
import logging
import operator
import sys
import time

from pini.utils import (
    plural, check_heart, to_time_t, str_to_seed, dprint, HOME,
    basic_repr, apply_filter)

from ..q_mgr import QtWidgets, QtCore

_LOGGER = logging.getLogger(__name__)
_PROGRESS_HEART = HOME.to_file('.progress_heart')


def _flush_unused_bars(stack_key):
    """Remove unused progress bars.

    Args:
        stack_key (str): replace any bars with this stack key
    """
    for _bar in copy.copy(sys.QT_PROGRESS_BAR_STACK):
        if _bar.is_finished() or _bar.stack_key == stack_key:
            _LOGGER.debug(
                ' - REMOVING BAR %s finished=%d', _bar, _bar.is_finished())
            sys.QT_PROGRESS_BAR_STACK.remove(_bar)
            _bar.close()
            _bar.deleteLater()


def _get_next_pos(stack_key):
    """Get next progress dialog position.

    This makes sure nested progress dialogs are stacked beneath each
    other.

    Args:
        stack_key (str): progress dialog uid

    Returns:
        (QPoint): next position
    """
    _LOGGER.debug(
        'GET NEXT BAR POS %s %s', stack_key, sys.QT_PROGRESS_BAR_STACK)

    if not sys.QT_PROGRESS_BAR_STACK:
        _LOGGER.debug(' - NO EXISTING BARS FOUND')
        return None

    _last_bar = sys.QT_PROGRESS_BAR_STACK[-1]
    _pos = _last_bar.pos() + QtCore.QPoint(0, 88)
    _LOGGER.debug(' - PLACING BELOW %s: %s', _last_bar, _pos)
    return _pos


class _ProgressDialog(QtWidgets.QDialog):
    """Simple dialog for showing progress of an interation."""

    def __init__(
            self, items, title='Processing {:d} item{}', col=None, show=True,
            pos=None, parent=None, stack_key='DefaultProgress', show_delay=None,
            plural_=None, raise_stop=True):
        """Constructor.

        Args:
            items (list): items to iterate
            title (str): progress dialog title
            col (QColor): progress bar colour
            show (bool): show progress bar
            pos (QPoint): override position
            parent (QDialog): parent dialog
            stack_key (str): dialog uid
            show_delay (float): delay in showing dialog (in secs)
            plural_ (str): override plural string in title
                (eg. 'es' for 'fixes')
            raise_stop (bool): raise StopIteration on complete
        """
        from pini import dcc, qt
        _flush_unused_bars(stack_key=stack_key)

        # Avoid batch mode seg fault
        if dcc.batch_mode():
            raise RuntimeError("Cannot create progress bar in batch mode")

        _items = items
        if isinstance(_items, (enumerate, collections.abc.Iterable)):
            _items = list(_items)
        self.items = _items

        self.stack_key = stack_key
        self.show_delay = show_delay
        self.raise_stop = raise_stop

        self.counter = 0
        self.last_update = time.time()
        self.start = time.time()
        self.durs = []
        self.info = ''
        self._display_pc = None
        self._pos = pos

        _parent = parent or dcc.get_main_window_ptr()
        _args = [_parent] if _parent else []
        super().__init__(*_args)

        _title = title.format(
            len(self.items), plural(self.items, plural_=plural_))
        self.setWindowTitle(_title)
        self.resize(408, 54)
        self._apply_pos()

        _col = col
        if not _col:
            _random = str_to_seed(title)
            _col = _random.choice(qt.BOLD_COLS)

        # Build ui
        self.grid_lyt = QtWidgets.QGridLayout(self)
        self.progress_bar = qt.CProgressBar(self)
        _size_policy = QtWidgets.QSizePolicy(
            QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        _size_policy.setHorizontalStretch(0)
        _size_policy.setVerticalStretch(0)
        _size_policy.setHeightForWidth(
            self.progress_bar.sizePolicy().hasHeightForWidth())
        self.progress_bar.setSizePolicy(_size_policy)
        self.progress_bar.setProperty("value", 0)
        self.grid_lyt.addWidget(self.progress_bar, 0, 0, 1, 1)
        self.progress_bar.set_col(_col)

        self._hidden = True
        if show and not show_delay:
            self._hidden = False
            self.show()

        sys.QT_PROGRESS_BAR_STACK.append(self)

    def _apply_pos(self):
        """Apply position."""
        from pini import qt
        if self._pos:
            _pos = self._pos - qt.to_p(self.size())/2
        else:
            _pos = _get_next_pos(stack_key=self.stack_key)
        if _pos:
            self.move(_pos)

    @property
    def cur_pc(self):
        """Calculate current percent complete.

        Returns:
            (float): percent complete
        """
        return round(100.0 * self.counter / max(len(self.items), 1))

    def close(self):
        """Garbage collection safe wrapper for close."""
        try:
            super().close()
        except RuntimeError:
            pass

    def _finalise(self):
        """Finalise this dialog."""
        if self in sys.QT_PROGRESS_BAR_STACK:
            sys.QT_PROGRESS_BAR_STACK.remove(self)

    def is_finished(self):
        """Test whether this dialog is finished.

        Returns:
            (bool): whether finished
        """
        if not self.isVisible():
            if self._hidden:
                return False
            return True
        return False

    def print_eta(self):
        """Print expected time remaining."""
        _n_remaining = len(self.items) - self.counter + 1
        _durs = self.durs[-5:]
        _avg_dur = sum(_durs) / len(_durs)
        _etr = _avg_dur * _n_remaining
        _eta = time.time() + _etr
        dprint(
            'Beginning {}/{}, frame_t={:.02f}s, etr={:.00f}s, '
            'eta={}{}'.format(
                self.counter, len(self.items), _avg_dur, _etr,
                time.strftime('%H:%M:%S', to_time_t(_eta)),
                self.info))

    def set_pc(self, percent):
        """Set percent complete.

        Args:
            percent (float): percent complete
        """
        while self.cur_pc <= percent:
            check_heart()
            self.__next__(update_ui=False)  # pylint: disable=unnecessary-dunder-call
        self.update_ui()

    def show(self):
        """Show this dialog."""

        # Show hidden progress bars above
        for _bar in sys.QT_PROGRESS_BAR_STACK:
            if _bar == self:
                break
            _bar.show()

        super().show()

    def update_ui(self):
        """Update interface."""
        from pini import qt
        qt.get_application().processEvents()

    def deleteLater(self):
        """Garbage collection safe wrapper for deleteLater."""
        try:
            super().deleteLater()
        except RuntimeError:
            pass

    def isVisible(self):
        """Garbage collection safe wrapper for isVisible."""
        try:
            return super().isVisible()
        except RuntimeError:
            return False

    def __iter__(self):
        return self

    def __len__(self):
        return len(self.items)

    def __next__(self, update_ui=True):

        from pini import qt

        _dur = time.time() - self.start
        if self._hidden and self.show_delay and _dur > self.show_delay:
            self.show()
            self._hidden = False
        _LOGGER.log(9, 'ITERATING %s %s', self.isVisible(), _dur)
        check_heart()
        check_heart(heart=_PROGRESS_HEART)

        if not self._hidden and not self.isVisible():
            self._finalise()
            raise qt.DialogCancelled

        # Apply update
        if self.cur_pc != self._display_pc:
            self.progress_bar.setValue(self.cur_pc)
            if update_ui:
                self.update_ui()
        self._display_pc = self.cur_pc

        # Increment item
        self.counter += 1
        try:
            _result = self.items[self.counter-1]
        except IndexError:
            self.close()
            self._finalise()
            if self.raise_stop:
                raise StopIteration
            return None

        _dur = time.time() - self.last_update
        self.durs.append(_dur)
        self.last_update = time.time()

        return _result

    def __repr__(self):
        return basic_repr(self, self.stack_key)


def close_all_progress_bars(filter_=None):
    """Close all progress bar dialogs.

    Args:
        filter_ (str): apply stack_key filter
    """
    _bars = list(sys.QT_PROGRESS_BAR_STACK)
    if filter_:
        _bars = apply_filter(
            _bars, filter_, key=operator.attrgetter('stack_key'))
    while _bars:
        _bar = _bars.pop()
        _bar.deleteLater()
        sys.QT_PROGRESS_BAR_STACK.remove(_bar)


@functools.wraps(_ProgressDialog.__init__)
def progress_bar(items, *args, **kwargs):
    """Show a progress bar dialog while iterating the given item list.

    Args:
        items (list): items to iterator

    Returns:
        (ProgressDialog): iterator which displays a progress dialog
    """
    from pini import dcc, qt
    _show = kwargs.get('show', True)
    if not _show:
        return items
    if dcc.batch_mode():
        _LOGGER.info('DISABLE PROGRESS BAR IN BATCH MODE')
        return items
    if not items:
        return items
    qt.get_application()
    return _ProgressDialog(items, *args, **kwargs)


@functools.wraps(_ProgressDialog.__init__)
def progress_dialog(
        title='Progress Dialog', stack_key='ProgressDialog', **kwargs):
    """Obtain a progress dialog interface.

    This is untethered to any data but can manually have its percentage
    complete set using ProgressDialog.set_pc method.

    Args:
        title (str): dialog title
        stack_key (str): override dialog unique identifier

    Returns:
        (ProgressDialog): progress dialog
    """
    _dialog = _ProgressDialog(
        range(100), title=title, stack_key=stack_key, raise_stop=False,
        **kwargs)
    _dialog.set_pc(0)
    return _dialog
