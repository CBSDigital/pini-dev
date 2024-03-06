"""Tools for managing the progress dialog."""

# pylint: disable=too-many-instance-attributes

import copy
import functools
import logging
import time

from pini.utils import (
    plural, check_heart, to_time_t, str_to_seed, dprint,
    SixIterable)

from ..q_mgr import QtWidgets, QtCore

_LOGGER = logging.getLogger('pini.qt')
_PROGRESS_BARS = []


def _get_next_pos(stack_key):
    """Get next progress dialog position.

    This makes sure nested progress dialogs are stacked beneath each
    other.

    Args:
        stack_key (str): progress dialog uid

    Returns:
        (QPoint): next position
    """

    # Flush out unused bars
    for _bar in copy.copy(_PROGRESS_BARS):
        if (
                not _bar.isVisible() or
                _bar.stack_key == stack_key
        ):
            _LOGGER.debug('REPLACING EXISTING BAR %s', _bar)
            _PROGRESS_BARS.remove(_bar)
            _bar.close()
            _bar.deleteLater()

    if not _PROGRESS_BARS:
        _LOGGER.debug('NO EXISTING BARS FOUND')
        return None

    _pos = _PROGRESS_BARS[-1].pos() + QtCore.QPoint(0, 88)
    _LOGGER.debug('USING EXISTING BAR POS')
    return _pos


class _ProgressDialog(QtWidgets.QDialog):
    """Simple dialog for showing progress of an interation."""

    def __init__(
            self, items, title='Processing {:d} item{}', col=None, show=True,
            pos=None, parent=None, stack_key='progress', show_delay=None,
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

        # Avoid batch mode seg fault
        if dcc.batch_mode():
            raise RuntimeError("Cannot create progress bar in batch mode")

        _items = items
        if isinstance(_items, (enumerate, SixIterable)):
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

        _parent = parent or dcc.get_main_window_ptr()
        _args = [_parent] if _parent else []
        super(_ProgressDialog, self).__init__(*_args)

        _title = title.format(
            len(self.items), plural(self.items, plural_=plural_))
        self.setWindowTitle(_title)
        self.resize(408, 54)

        if pos:
            _pos = pos - qt.to_p(self.size())/2
        else:
            _pos = _get_next_pos(stack_key=stack_key)
        if _pos:
            self.move(_pos)

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

        _PROGRESS_BARS.append(self)

    @property
    def cur_pc(self):
        """Calculate current percent complete.

        Returns:
            (float): percent complete
        """
        return 100.0 * self.counter / max(len(self.items), 1)

    def isVisible(self):
        """Garbage collection safe wrapper for isVisible."""
        try:
            return super(_ProgressDialog, self).isVisible()
        except RuntimeError:
            return False

    def close(self):
        """Garbage collection safe wrapper for close."""
        try:
            super(_ProgressDialog, self).close()
        except RuntimeError:
            pass

    def deleteLater(self):
        """Garbage collection safe wrapper for deleteLater."""
        try:
            super(_ProgressDialog, self).deleteLater()
        except RuntimeError:
            pass

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
            self.next(update_ui=False)
        self.update_ui()

    def update_ui(self):
        """Update interface."""
        from pini import qt
        qt.get_application().processEvents()

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
        _LOGGER.debug('ITERATING %s %s', self.isVisible(), _dur)
        check_heart()

        if not self._hidden and not self.isVisible():
            raise qt.DialogCancelled

        self.progress_bar.setValue(self.cur_pc)
        if update_ui:
            self.update_ui()

        self.counter += 1
        try:
            _result = self.items[self.counter-1]
        except IndexError:
            self.close()
            if self.raise_stop:
                raise StopIteration
            return None

        _dur = time.time() - self.last_update
        self.durs.append(_dur)
        self.last_update = time.time()

        return _result

    next = __next__


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


def progress_dialog(
        title='Progress Dialog', stack_key='ProgressDialog', col=None,
        parent=None):
    """Obtain a progress dialog interface.

    This is untethered to any data but can manually have its percentage
    complete set using ProgressDialog.set_pc method.

    Args:
        title (str): dialog title
        stack_key (str): override dialog unique identifier
        col (CColor): dialog colour
        parent (QWidget): parent widget

    Returns:
        (ProgressDialog): progress dialog
    """
    _dialog = _ProgressDialog(
        range(100), title=title, stack_key=stack_key, raise_stop=False, col=col,
        parent=parent)
    _dialog.set_pc(0)
    return _dialog
