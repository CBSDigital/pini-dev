"""Tools for managing sequences.

A sequence is a folder on disk containing a number of shots.
"""

import copy
import logging
import operator

import lucidity

from pini import icons
from pini.utils import single, apply_filter

from .. import cp_settings_elem
from ...cp_utils import extract_template_dir_data

_LOGGER = logging.getLogger(__name__)


class CPSequenceBase(cp_settings_elem.CPSettingsLevel):
    """Represents a sequence on disk."""

    def __init__(self, path, job=None, template=None):
        """Constructor.

        Args:
            path (str): path within sequence
            job (CPJob): override sequence job
            template (CPTemplate): force template
        """
        from pini import pipe

        # Set job
        self.job = job
        if not self.job:
            _job = pipe.CPJob(path)
            self.job = pipe.obt_job(_job.name)

        # Read template
        self._tmpl = template or single(self.job.templates['sequence_path'])
        try:
            _path, self.data = extract_template_dir_data(
                path=path, template=self._tmpl, job=self.job)
        except lucidity.ParseError as _exc:
            raise ValueError(f'Lucidity parse error {path}') from _exc
        super().__init__(_path)

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
                f'Create new sequence "{self.name}" in "{self.job.name}"?'
                f'\n\n{self.path}',
                icon=icons.find('Plus'), title='Create sequence',
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

        # Find shot paths
        _paths = self._read_shot_paths()
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

    def _read_shot_paths(self):
        """Get a list of shot paths in this sequence."""
        raise NotImplementedError

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
