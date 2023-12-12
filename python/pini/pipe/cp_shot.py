"""Tools for managing shots."""

# pylint: disable=too-many-instance-attributes

import sys
import logging

import lucidity

from pini import icons, dcc
from pini.utils import abs_path

from .cp_job import CPJob, obtain_job
from .cp_entity import CPEntity
from .cp_utils import validate_tokens

_LOGGER = logging.getLogger(__name__)


class CPShot(CPEntity):
    """Represents a shot dir on disk."""

    profile = 'shot'
    idx = None
    is_asset = False
    is_shot = True

    def __init__(self, path, job=None):
        """Constructor.

        Args:
            path (str): path inside shot
            job (CPJob): force parent job
        """
        from pini import pipe
        _LOGGER.debug('SHOT INIT')

        # Set job
        if job:
            self.job = job
        else:
            _job = CPJob(path)
            self.job = obtain_job(_job.name)

        # Prepare template
        self.template = self.job.find_template('entity_path', profile='shot')
        self.template = self.template.apply_data(job_path=self.job.path)
        _LOGGER.debug(' - TMPL %s', self.template)
        assert isinstance(self.template, pipe.CPTemplate)

        # Crop path to shot depth
        _path = abs_path(path)
        _depth = self.template.pattern.count('/') + 1
        _path = '/'.join(_path.split('/')[:_depth])
        _LOGGER.debug(' - PATH %s', _path)

        # Parse template for data
        try:
            self.data = self.template.parse(_path)
        except lucidity.ParseError:
            raise ValueError('lucidity rejected path '+_path)
        validate_tokens(data=self.data, job=self.job)
        self.shot = self.data['shot']
        self.name = self.shot
        self.label = '{}/{}'.format(self.job.name, self.name)

        # Determine prefix
        self.prefix = self.name
        while self.prefix and self.prefix[-1].isdigit():
            self.prefix = self.prefix[:-1]

        # Determine sequence
        if 'sequence' in self.data:
            self.sequence = self.data['sequence']
            _, self.idx = _parse_shot_name(self.name)
        else:
            self.sequence, self.idx = _parse_shot_name(self.name)
        self.entity_type = self.sequence

        super(CPShot, self).__init__(_path)

    @property
    def _settings_parent(self):
        """Obtain settings parent object.

        Returns:
            (CPSettingsLevel): settings parent
        """
        if self.job.uses_sequence_dirs:
            return self.to_sequence()
        return self.job

    def create(self, force=False, parent=None, shotgrid_=True):
        """Create this shot.

        Args:
            force (bool): create shot without warning dialogs
            parent (QDialog): parent for confirmation dialogs
            shotgrid_ (bool): register in shotgrid (if available)
        """
        from pini import qt

        _LOGGER.debug('CREATE SHOT %s', self)
        if self.job.uses_sequence_dirs:
            _seq = self.to_sequence()
            if not _seq.exists():
                _seq.create(force=force, parent=parent, shotgrid_=shotgrid_)
            assert _seq.exists()
            _LOGGER.debug(' - SEQUENCE EXISTS %s', _seq)

        # Confirm
        if not force:
            qt.ok_cancel(
                'Create new shot {} in {}?\n\n{}'.format(
                    self.name, self.job.name, self.path),
                icon=icons.find('Plus'), title='Create Shot',
                parent=parent)

        # Execute callback
        _create_shot_callback = getattr(sys, 'PINI_CREATE_SHOT_CALLBACK', None)
        if _create_shot_callback:
            _create_shot_callback(shot=self)

        super(CPShot, self).create(
            force=True, parent=parent, shotgrid_=shotgrid_)

    def to_sequence(self):
        """Get this shot's corresponding sequence object.

        Returns:
            (CPSequence): sequence object
        """
        from pini import pipe
        return pipe.CPSequence(self.path, job=self.job)


def _parse_shot_name(shot):
    """Read sequence name and shot number from shot.

    eg. dev000 -> dev, 0

    Args:
        shot (str): name of shot to parse

    Returns:
        (tuple): sequence name, shot number
    """
    _seq = shot
    _idx_str = ''
    while _seq and _seq[-1].isdigit():
        _idx_str = _seq[-1] + _idx_str
        _seq = _seq[:-1]
    if not _idx_str:
        return _seq, None
    return _seq, int(_idx_str)


def apply_create_shot_callback(func):
    """Apply create shot callback.

    This is executed on shot creation.

    Args:
        func (fn): function to execute
    """
    sys.PINI_CREATE_SHOT_CALLBACK = func


def cur_shot(catch=True):
    """Get the current shot (if any).

    Args:
        catch (bool): return None if no current shot

    Returns:
        (CPShot): current shot
    """
    try:
        return CPShot(dcc.cur_file())
    except ValueError:
        if catch:
            return None
        raise ValueError('No current shot')


def to_shot(path):
    """Obtain a shot object from the given path.

    Args:
        path (str): path to read shot from

    Returns:
        (CPShot|None): shot (if any)
    """
    try:
        return CPShot(path)
    except ValueError:
        return None
