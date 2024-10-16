"""Tools for managing shotgrid asset and shot elements."""

import operator
import logging

from pini.utils import (
    basic_repr, strftime, Dir, to_time_f)

from ..sg_utils import sg_cache_to_file
from . import sgc_container, sgc_utils

_LOGGER = logging.getLogger(__name__)


class _SGCEntity(sgc_container.SGCContainer):
    """Base class for asset/shot element containers."""

    PROFILE = None

    _cache_fmt = None

    def __init__(self, data, entity, entity_type):
        """Constructor.

        Args:
            data (dict): element data
            entity (str): entity name
            entity_type (str): entity type
        """
        assert self.PROFILE

        self.name = entity
        self.entity_type = entity_type
        self.uid = f'{entity_type}.{entity}'

        super().__init__(data=data)

    @property
    def cache_fmt(self):
        """Obtainn cache path format string.

        Returns:
            (str): cache format
        """
        if not self._cache_fmt:
            from pini import pipe
            _job = self.proj.job
            _LOGGER.debug(' - JOB %s', _job)
            _LOGGER.debug(' - PROFILE %s', self.PROFILE)
            _tmpl = _job.find_template('entity_path', profile=self.PROFILE)
            _LOGGER.debug(' - TMPL %s', _tmpl)
            _root = Dir(_tmpl.format(
                job_path=_job.path, asset_type=self.entity_type,
                asset=self.name, shot=self.name, sequence=self.entity_type))
            _LOGGER.debug(' - ROOT %s', _root.path)
            _cfg_name = _job.cfg['name']
            _cache_dir = _root.to_subdir(
                f'.pini/SGC/P{pipe.VERSION}_{_cfg_name}')
            self._cache_fmt = _cache_dir.to_file('{func}.pkl').path
            _LOGGER.debug(' - CACHE FMT %s', self._cache_fmt)
        return self._cache_fmt

    @property
    def pub_files(self):
        """Obtain list of pub files in this entity.

        Returns:
            (SGCPubFile list): pub files
        """
        return self.find_pub_files()

    @property
    def tasks(self):
        """Obtain list of tasks in this entity.

        Returns:
            (SGCTask list): tasks
        """
        return self.find_tasks()

    def find_pub_files(self, force=False, **kwargs):
        """Search pub files in this entity.

        Args:
            force (bool): reread cached data

        Returns:
            (SGCPubFile list): pub files
        """
        _pub_files = []
        for _pub_file in self._read_pub_files(force=force):
            if not sgc_utils.passes_filters(
                    _pub_file, filter_attr='path', **kwargs):
                continue
            _pub_files.append(_pub_file)
        return _pub_files

    def find_tasks(self):
        """Search tasks in this entity.

        Returns:
            (SGCTask list): tasks
        """
        return self._read_tasks()

    def _read_pub_files(self, force=False):
        """Read pub files in this entity.

        Args:
            force (bool): force reread from shotgrid

        Returns:
            (SGCPubFile list): pub files
        """
        _LOGGER.debug('READ PUB FILES %s', self)

        _last_t = self._read_elems_updated_t(sgc_container.SGCPubFile)
        if not _last_t:
            return []
        _LOGGER.debug(' - LAST T %s', strftime('nice', _last_t))

        _last_t_c, _pub_files_c = self._build_pub_files_cache(force=force)
        if _last_t_c != _last_t:
            _last_t_c, _pub_files_c = self._build_pub_files_cache(
                force=True)
            _LOGGER.info(
                ' - T CMP last="%s" cache="%s"',
                strftime('nice', _last_t),
                strftime('nice', _last_t_c))
            assert _last_t_c == _last_t
        return _pub_files_c

    @sg_cache_to_file
    def _build_pub_files_cache(self, force=False):
        """Build pub files cache for this entity.

        This reads all pub file elements and then tests if each one maps
        to a valid pipeline output. If so, latest status, and template
        and version stream paths are applied. The last update time is also
        returned to mark whether this cache needs to be regenerated.

        Args:
            force (bool): force rebuild cached data

        Returns:
            (tuple): last update time, pub file list
        """
        from pini import pipe

        _LOGGER.info(' - BUILD PUB FILES DATA %s', self)
        _LOGGER.info(' - CACHE FMT %s', self.cache_fmt)

        # Read pub file elements
        _pub_files = self._read_elems(
            sgc_container.SGCPubFile, force=force)
        assert _pub_files
        _LOGGER.debug(' - FOUND %d PUB FILES', len(_pub_files))
        _last_t = to_time_f(max(
            _pub_file.updated_at for _pub_file in _pub_files))

        # Validate output path
        _latest_map = {}
        for _pub_file in sorted(
                _pub_files, key=operator.attrgetter('path')):
            _LOGGER.debug(' - CHECKING PUB FILE %s', _pub_file)
            _out = pipe.to_output(_pub_file.path, catch=True)
            if _out and _out.entity.name != self.name:
                _LOGGER.debug(
                    '   - ENTITY NAME MISMATCH %s != %s', _out.entity.name,
                    self.name)
                _out = None
            _LOGGER.debug('   - OUT %s', _out)
            _pub_file.validated = bool(_out)
            _LOGGER.debug('   - VALIDATED %d', _pub_file.validated)
            if _out:
                _pub_file.stream = _out.to_stream()
                _pub_file.template = _out.template.source.pattern
                _latest_map[_pub_file.stream] = _pub_file

        # Mark latest
        for _pub_file in _pub_files:
            if _pub_file.stream:
                _pub_file.latest = _pub_file is _latest_map[_pub_file.stream]

        return _last_t, _pub_files

    def _read_tasks(self, force=False):
        """Read tasks inside this entity.

        Args:
            force (bool): force rebuild cached data

        Returns:
            (SGCTask list): tasks
        """
        return self._read_elems(sgc_container.SGCTask, force=force)

    def to_filter(self):
        """Build shotgrid search filter from this entry.

        Returns:
            (tuple): filter
        """
        return 'entity', 'is', self.to_entry()


class SGCAsset(_SGCEntity):
    """Represents an asset."""

    PROFILE = 'asset'
    ENTITY_TYPE = 'Asset'
    FIELDS = (
        'sg_asset_type', 'code', 'sg_status_list', 'updated_at',
        'project')

    def __init__(self, data):
        """Constructor.

        Args:
            data (dict): shotgrid data
        """
        self.asset_type = data['sg_asset_type']
        self.asset = data['code']
        super().__init__(
            data, entity=self.asset, entity_type=self.asset_type)

    def __repr__(self):
        return basic_repr(
            self, f'{self.proj.name}.{self.asset_type}.{self.asset}')


class SGCShot(_SGCEntity):
    """Represents a shot."""

    PROFILE = 'shot'
    ENTITY_TYPE = 'Shot'
    FIELDS = (
        'sg_head_in', 'code', 'sg_sequence', 'sg_status_list',
        'updated_at', 'sg_has_3d', 'project')

    def __init__(self, data):
        """Constructor.

        Args:
            data (dict): shotgrid data
        """
        if not data.get('sg_sequence'):
            raise ValueError('No sequence')
        self.sequence = data['sg_sequence']['name']
        self.shot = data['code']
        super().__init__(
            data, entity=self.shot, entity_type=self.sequence)

    def __repr__(self):
        return basic_repr(
            self, f'{self.proj.name}:{self.shot}')
