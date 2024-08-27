"""Tools for managing sequences.

A sequence is a folder on disk containing a number of shots.
"""

import copy
import logging
import operator

import lucidity

from pini import icons
from pini.utils import single, apply_filter

from . import cp_settings
from .cp_job import CPJob, obtain_job
from .cp_utils import extract_template_dir_data

_LOGGER = logging.getLogger(__name__)


class CPSequence(cp_settings.CPSettingsLevel):
    """Represents a sequence on disk."""

    def __init__(self, path, job=None, template=None):
        """Constructor.

        Args:
            path (str): path within sequence
            job (CPJob): override sequence job
            template (CPTemplate): force template
        """

        # Set job
        self.job = job
        if not self.job:
            _job = CPJob(path)
            self.job = obtain_job(_job.name)

        # Read template
        self._tmpl = template or single(self.job.templates['sequence_path'])
        try:
            _path, self.data = extract_template_dir_data(
                path=path, template=self._tmpl, job=self.job)
        except lucidity.ParseError:
            raise ValueError('Lucidity parse error {}'.format(path))
        super(CPSequence, self).__init__(_path)

        self.sequence = self.data['sequence']
        self.name = self.sequence

    @property
    def _settings_parent(self):
        """Obtain settings parent object (job).

        Returns:
            (CPSettingsLevel): settings parent
        """
        return self.job

    def create(self, shotgrid_=True, parent=None, force=False):
        """Create this sequence.

        Args:
            shotgrid_ (bool): register sequence in shotgrid (if available)
            parent (QDialog): parent for confirmation dialogs
            force (bool): create sequence without confirmation dialogs
        """
        from pini import pipe
        _LOGGER.debug('CREATE SEQ %s', self)

        # Obtain seq dir
        _LOGGER.debug(' - SEQ DIR %s', self.path)
        assert not self.exists()

        # Confirm
        if not force:
            from pini import qt
            qt.ok_cancel(
                'Create new sequence {} in {}?\n\n{}'.format(
                    self.name, self.job.name, self.path),
                icon=icons.find('Plus'), title='Create Sequence',
                parent=parent)

        self.mkdir()

        # Register in shotgrid
        if shotgrid_ and pipe.SHOTGRID_AVAILABLE:
            from pini.pipe import shotgrid
            shotgrid.create_sequence(self, force=True)

    def find_shots(self, filter_=None, class_=None):
        """Read shots in the given sequence.

        Args:
            filter_ (str): filter by shot name
            class_ (class): override shot class

        Returns:
            (CPShot list): sequence shots
        """
        _shots = self._read_shots(class_=class_)
        if filter_:
            _shots = apply_filter(
                _shots, filter_, key=operator.attrgetter('name'))
        return _shots

    def _read_shots(self, class_=None):
        """Read shots within this sequence.

        Args:
            class_ (class): override shot class

        Returns:
            (CPShot list): shots
        """
        from pini import pipe
        _LOGGER.debug('READ SHOTS')

        _class = class_ or pipe.CPShot

        # Set up template
        _tmpl = self.job.find_template('entity_path', profile='shot')
        _tmpl = _tmpl.apply_data(job_path=self.job.path, sequence=self.name)
        _LOGGER.debug(' - TEMPLATE %s path_type=%s', _tmpl, _tmpl.path_type)

        # Find shot paths
        if pipe.MASTER == 'disk':
            _paths = pipe.glob_template(template=_tmpl, job=self.job)
        elif pipe.MASTER == 'shotgrid':
            _paths = [_shot for _shot in self.job.read_shots_sg()
                      if _shot.sequence == self.name]
            _LOGGER.debug(' - PATHS %s', _paths)
        else:
            raise ValueError(pipe.MASTER)
        _LOGGER.debug(' - FOUND %d PATHS %s', len(_paths), _paths)

        # Build shot objects
        _shots = []
        for _path in _paths:
            try:
                _shot = _class(_path, job=self.job)
            except ValueError:
                continue
            _shots.append(_shot)

        return _shots

    def to_shot(self, name):
        """Create a shot object using this sequence's data.

        Args:
            name (str): shot name

        Returns:
            (CPShot): shot
        """
        from pini import pipe
        _tmpl = self.job.find_template('entity_path', profile='shot')
        _data = copy.copy(self.data)
        _data['shot'] = name
        _data['job_path'] = self.job.path
        _path = _tmpl.format(_data)
        return pipe.CPShot(_path, job=self.job)


def cur_sequence():
    """Obtain current sequence.

    Returns:
        (CPSequence|None): sequence (if any)
    """
    from pini import dcc
    _path = dcc.cur_file()
    if not _path:
        return None
    try:
        return CPSequence(_path)
    except ValueError:
        return None
