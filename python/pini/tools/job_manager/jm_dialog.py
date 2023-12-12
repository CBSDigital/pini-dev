"""Tools for managing the Shot Builder interface."""

import logging

from pini import qt, pipe, icons
from pini.tools import usage, error
from pini.utils import File, single, str_to_ints, plural

_LOGGER = logging.getLogger(__name__)

_DIR = File(__file__).to_dir()
UI_FILE = _DIR.to_file('job_manager.ui').path
TITLE = 'Job Manager'
ICON = icons.find('Bread')

_BLACKEN = 0.0
_JOB_COL = qt.to_col('HotPink').blacken(_BLACKEN)
_SEQ_COL = qt.to_col('PeachPuff').blacken(_BLACKEN)
_SHOT_COL = qt.to_col('DarkGrey').blacken(_BLACKEN)


class _JobManager(qt.CUiDialog):
    """Interface for building shots."""

    def __init__(self, job=None):
        """Constructor.

        Args:
            job (CPJob): job to select
        """
        self._staged_shots = []
        self.sequence = None
        self.level = None

        self._seq_prefix = None
        self._valid_prefix = None

        super(_JobManager, self).__init__(ui_file=UI_FILE)
        self.ui.ShotsTree.clear()
        self.set_window_icon(ICON)

        self._redraw__Job(job=job)
        self._callback__ShotsTabs()
        self._callback__ShotsTree()

        self.ui.SSettingsTab.setEnabled(False)
        self.ui.ShotsTabs.set_tab_enabled('Settings', False)

    def _redraw__Job(self, job=None):

        _data = pipe.CACHE.jobs
        _labels = [_job.name for _job in pipe.CACHE.jobs]

        # Determine selected item
        _select = job.name if job else None
        if not _select and pipe.cur_job():
            _select = pipe.cur_job().name
        if not _select:
            _recent = pipe.recent_work()
            if _recent:
                _select = _recent[0].job.name

        self.ui.Job.set_items(_labels, data=_data, select=_select)

    def _redraw__ShotsTree(self):

        _LOGGER.debug('REDRAW ShotsTree')

        _tab = self.ui.ShotsTabs.current_tab_text()
        _sel = self.ui.ShotsTree.selected_data()
        _job = self.ui.Job.selected_data()

        # Get list of seqs/shots
        _seq_text = self.ui.CSequence.currentText()
        _sel_seq = _job.to_sequence(_seq_text) if _seq_text else None
        _seqs = sorted([_seq for _seq in (set(_job.sequences) | {_sel_seq})
                        if _seq])
        _LOGGER.debug(' - SEQS %s', _seqs)
        _shots = sorted(set(list(_job.shots) + self._staged_shots))
        _LOGGER.debug(' - SHOTS %s', _shots)

        # Check if this not is a fresh build, maintain collapsed items
        _data = self.ui.ShotsTree.all_data()
        _fresh = _data and _data[0] != _job
        _LOGGER.debug(' - FRESH %s', _fresh)
        _collapsed = []
        if _fresh:
            self._staged_shots = []
        else:
            _collapsed = self._read_collapsed_items(sel_seq=_sel_seq)
        _LOGGER.debug(' - COLLAPSED %s', _collapsed)

        # Build root
        self.ui.ShotsTree.clear()
        _job_item = qt.CTreeWidgetItem(
            _job.name, col=_JOB_COL, data=_job)
        self.ui.ShotsTree.addTopLevelItem(_job_item)

        for _seq in _seqs:

            # Create sequence
            _col = _SEQ_COL
            if _seq not in _job.sequences:
                if _tab != 'Create':
                    continue
                _col = _col.whiten(0.8)
            _seq_item = qt.CTreeWidgetItem(_seq.name, col=_col, data=_seq)
            _job_item.addChild(_seq_item)

            # Add shots
            _seq_shots = [_shot for _shot in _shots
                          if _shot.sequence == _seq.name]
            for _shot in _seq_shots:
                _col = _SHOT_COL
                if _shot not in _job.shots:
                    if _tab != 'Create':
                        continue
                    _col = _col.whiten(0.8)
                _shot_item = qt.CTreeWidgetItem(
                    _shot.name, data=_shot, col=_col)
                _seq_item.addChild(_shot_item)
            if _seq not in _collapsed:
                _seq_item.setExpanded(True)

        _job_item.setExpanded(True)

    def _read_collapsed_items(self, sel_seq):
        """Read collapsed ShotsTree items so their state can be restored.

        Args:
            sel_seq (CPSequence): selected sequence

        Returns:
            (CPJob|CPSequence list): collapsed items
        """
        _collapsed = []
        for _item in self.ui.ShotsTree.all_items():
            if _item.isExpanded():
                continue
            if not _item.childCount():
                continue
            _data = _item.get_data()
            if _data == sel_seq:
                continue
            _collapsed.append(_data)
        return _collapsed

    def _redraw__CSequence(self):
        _job = self.ui.Job.selected_data()
        _labels = [_seq.name for _seq in _job.sequences]
        self.ui.CSequence.set_items(_labels, data=_job.sequences)

    def _redraw__SSettingsTab(self):

        _sel = self.ui.ShotsTree.selected_data()
        if isinstance(_sel, (pipe.CPJob, pipe.CPSequence, pipe.CPShot)):
            _text = 'Set {} config'.format(_sel.name)
            self.level = _sel
        else:
            _text = 'Select job, sequence or shot to apply config'
        self.ui.SLevelText.setText(_text)

    def _callback__ShotsTabs(self):
        _tab = self.ui.ShotsTabs.current_tab_text()
        # print 'CALLBACK SHOTS TAB', _tab
        self.ui.ShotsTree.redraw()
        if _tab == 'Settings':
            self.ui.SSettingsTab.redraw()

    def _callback__Job(self):
        self._redraw__CSequence()
        self._callback__CShotsText()

    def _callback__ShotsTree(self):

        _tab = self.ui.ShotsTabs.current_tab_text()
        _sel = self.ui.ShotsTree.selected_data()
        _LOGGER.debug('CHANGED SHOT TREE SELECTION %s', _sel)

        if _tab == 'Create':

            # Check if a seq/prefix was selected
            _prefix = None
            _seq = None
            if isinstance(_sel, pipe.CPJob) or _sel is None:
                pass
            elif isinstance(_sel, pipe.CPShot):
                _seq = _sel.to_sequence()
                _prefix = _sel.prefix
            elif isinstance(_sel, pipe.CPSequence):
                _seq = _sel
            else:
                raise ValueError(_sel)

            if _seq:
                self.ui.CSequence.select_data(_seq)
            if _prefix:
                self.ui.CPrefix.setText(_prefix)

        elif _tab == 'Settings':
            self.ui.SSettingsTab.redraw()

        else:
            raise ValueError(_tab)

    def _callback__CSequence(self):

        _LOGGER.debug('CALLBACK Sequence')
        _job = self.ui.Job.selected_data()
        self.sequence = self.ui.CSequence.selected_data()
        _seq_text = self.ui.CSequence.currentText()
        if not self.sequence and _seq_text:
            _LOGGER.debug(' - SEQ TEXT %s', _seq_text)
            self.sequence = _job.to_sequence(_seq_text)
        _LOGGER.debug(' - SEQUENCE %s', self.sequence)

        # Apply prefix
        _shots = self.sequence.find_shots() if self.sequence else []
        self._seq_prefix = single({_shot.prefix for _shot in _shots},
                                  catch=True)
        _LOGGER.debug(' - SEQ PREFIX %s', self._seq_prefix)
        if self._seq_prefix:
            _prefix = self._seq_prefix
        else:
            _prefix = self.sequence.name.lower()[:3] if self.sequence else ''
        self.ui.CPrefix.setText(_prefix)
        self.ui.CPrefix.setEnabled(not bool(self._seq_prefix))
        self.ui.CPrefixLocked.setVisible(bool(self._seq_prefix))

        self.ui.CSequenceCreate.setEnabled(self.sequence not in _job.sequences)

        self._callback__CPrefix()
        self._callback__CShotsText()

    def _callback__CShotsText(self):

        _job = self.ui.Job.selected_data()
        _shots_text = self.ui.CShotsText.text()
        _prefix = self.ui.CPrefix.text()
        _seq = self.ui.CSequence.currentText()

        # Process shot indices
        try:
            _idxs = sorted(str_to_ints(_shots_text, inc=10))
        except ValueError:
            _idxs = []
            _failed = True
        else:
            _failed = not bool(_idxs)
        self.ui.CShotsWarning.setVisible(_failed)

        _LOGGER.debug('EDIT SHOTS TEXT %s %s', _shots_text, _idxs)
        self._staged_shots = []
        if _prefix and self._valid_prefix:
            for _idx in _idxs:
                _shot = _job.to_shot(sequence=_seq, shot='{}{:03d}'.format(
                    _prefix, _idx))
                if not _shot or _shot in _job.shots:
                    continue
                self._staged_shots.append(_shot)
        _LOGGER.debug(' - STAGED SHOTS %s', self._staged_shots)

        # Trigger updates
        self._redraw__ShotsTree()
        self.ui.CShotsCreate.setEnabled(bool(self._staged_shots))

    def _callback__CPrefix(self):

        _LOGGER.debug('CALLBACK Prefix')
        _prefix = self.ui.CPrefix.text()
        try:
            _validate_prefix(_prefix, sequence=self.sequence)
        except ValueError as _exc:
            _fail = str(_exc)
        else:
            _fail = None
        for _elem in [self.ui.CPrefixWarning, self.ui.CPrefixWarningText]:
            _elem.setVisible(bool(_fail))
        if _fail:
            self.ui.CPrefixWarningText.setText(_fail)
        self._valid_prefix = bool(not _fail)

        self._callback__CShotsText()

    def _callback__CSequenceCreate(self):

        self.sequence.create(parent=self)
        self._callback__CShotsText()

    @usage.get_tracker('JobManager.ShotsCreate')
    def _callback__CShotsCreate(self):

        _job = self.ui.Job.selected_data()
        _seq = self.ui.CSequence.currentText()

        # Build shots
        qt.ok_cancel(
            msg='Create {:d} shot{} in {}/{}?'.format(
                len(self._staged_shots), plural(self._staged_shots),
                _job.name, _seq),
            parent=self, title='Create Shots', icon=icons.find('Plus'))
        _LOGGER.info('CREATE SHOTS %s', self._staged_shots)
        for _shot in qt.progress_bar(
                self._staged_shots, 'Creating {:d} shot{}', parent=self):
            _shot.create(force=True)

        # Update ui
        pipe.CACHE.reset()
        self._redraw__ShotsTree()
        self._callback__CShotsText()
        self.ui.CSequence.select_text(_seq)

    def _context__ShotsTree(self, menu):

        _dir = self.ui.ShotsTree.selected_data()
        print('DIR', _dir)
        if not _dir:
            return

        if isinstance(_dir, pipe.CPJob):
            _label = 'Job {}'.format(_dir.name)
        elif isinstance(_dir, pipe.CPSequence):
            _label = 'Sequence {}'.format(_dir.name)
        elif isinstance(_dir, pipe.CPShot):
            _label = 'Shot {}'.format(_dir.name)
        else:
            raise ValueError(_dir)
        menu.add_label(_label)
        menu.add_separator()
        menu.add_dir_actions(_dir)


def _validate_prefix(prefix, sequence):
    """Validate the given shot prefix.

    Args:
        prefix (str): prefix to validate
        sequence (CSequence): parent sequence
    """
    _LOGGER.debug('VALIDATE PREFIX %s %s', prefix, sequence)
    if not sequence:
        return

    _job = sequence.job

    if not prefix:
        raise ValueError('No prefix entered')

    # Check for prefix already in use (don't bother checking existing prefixes)
    for _shot in sequence.shots:
        if _shot.prefix == prefix:
            return

    # Check name
    if not prefix.islower():
        raise ValueError('Prefix must be lower case')
    if len(prefix) != 3:
        raise ValueError('Prefix must be 3 chars ({} is {:d})'.format(
            prefix, len(prefix)))
    if prefix[-1].isdigit():
        raise ValueError('Prefix cannot end with a number')
    if prefix[0].isdigit():
        raise ValueError('Prefix cannot start with a number')

    # Validate token
    _shot = '{}000'.format(prefix)
    pipe.validate_token(token='shot', value=_shot, job=_job)

    # Check for name clash
    for _shot in _job.shots:
        if _shot.to_sequence() == sequence:
            continue
        if _shot.prefix == prefix:
            raise ValueError(
                'Prefix {} is already used in sequence {}'.format(
                    prefix, _shot.sequence))


@error.catch
def launch(job=None):
    """Launch the Shot Builder interface.

    Args:
        job (CPJob): job to select

    Returns:
        (ShotBuilder): interface instance
    """
    from pini.tools import job_manager
    _LOGGER.debug('LAUNCH SHOT MANAGER admin=%d', pipe.admin_mode())

    if not pipe.admin_mode():
        raise error.HandledError(
            'You do not have permission to use JobManager.\n\nAsk your lead '
            'or pipeline administrator if you want to be granted access.')

    job_manager.DIALOG = _JobManager(job=job)
    return job_manager.DIALOG
