"""Tools for managing shotgrid asset and shot elements."""

import operator
import logging
import time

from pini.utils import (
    basic_repr, strftime, Dir, to_time_f, single, to_str)

from ..sg_utils import sg_cache_to_file, sg_cache_result
from . import sgc_elems, sgc_utils, sgc_elem

_LOGGER = logging.getLogger(__name__)


class _SGCEntity(sgc_elem.SGCElem):
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

    def find_pub_file(self, match=None, catch=False, **kwargs):
        """Find pub file within this entity.

        Args:
            match (Path|str): token to match
            catch (bool): no error if fail to match pub file

        Returns:
            (SGCPubFile): matching pub file
        """
        _LOGGER.debug('FIND PUB FILE %s %s', match, kwargs)
        _pub_files = self.find_pub_files(**kwargs)
        if len(_pub_files) == 1:
            return single(_pub_files)
        _LOGGER.debug(' - FOUND %d PUB FILES', len(_pub_files))

        # Try item/path matches
        _matches = [
            _pub_file for _pub_file in _pub_files
            if match in (_pub_file, _pub_file.path, _pub_file.id_)]
        if len(_matches) == 1:
            return single(_matches)
        _LOGGER.debug(' - MATCH %d PUB FILES', len(_matches))

        # Try string (eg. path) matches
        _match_s = to_str(match)
        _LOGGER.debug(' - MATCH S %s', _match_s)
        _s_matches = [
            _pub_file for _pub_file in _pub_files
            if _match_s in (_pub_file.path, )]
        if len(_s_matches) == 1:
            return single(_s_matches)
        _LOGGER.debug(' - S MATCHED %d PUB FILES', len(_s_matches))

        if catch:
            return None
        raise ValueError(match, kwargs)

    def find_pub_files(self, task=None, force=False, **kwargs):
        """Search pub files in this entity.

        Args:
            task (str): filter by task
            force (bool): reread cached data

        Returns:
            (SGCPubFile list): pub files
        """
        _kwargs = kwargs
        if task is not None:
            _kwargs['task'] = task
        _pub_files = []
        for _pub_file in self._read_pub_files(force=force):
            if not sgc_utils.passes_filters(
                    _pub_file, filter_attr='path', **_kwargs):
                continue
            _pub_files.append(_pub_file)
        return _pub_files

    def find_task(self, match=None, catch=False, **kwargs):
        """Find a task within this entity.

        Args:
            match (Path|str): token to match
            catch (bool): no error if fail to match task

        Returns:
            (SGCTask): matching task
        """
        _LOGGER.debug('FIND TASK %s %s', match, kwargs)

        _kwargs = kwargs
        if hasattr(match, 'step'):
            _kwargs['step'] = _kwargs.get('step', match.step)
        if hasattr(match, 'task'):
            _kwargs['task'] = _kwargs.get('task', match.task)

        _tasks = self.find_tasks(**_kwargs)
        if len(_tasks) == 1:
            return single(_tasks)
        _LOGGER.debug(' - FOUND %d TASKS', len(_tasks))

        _matches = [
            _task for _task in _tasks
            if match in (_task.name, )]
        if len(_matches) == 1:
            return single(_matches)
        _LOGGER.debug(' - MATCHED %d TASKS', len(_matches))

        if catch:
            return None
        raise ValueError(match, kwargs)

    def find_tasks(self, **kwargs):
        """Search tasks in this entity.

        Returns:
            (SGCTask list): tasks
        """
        _LOGGER.debug('FIND TASKS %s', kwargs)
        _tasks = []
        for _task in self._read_tasks():
            if not sgc_utils.passes_filters(_task, **kwargs):
                continue
            _tasks.append(_task)
        _LOGGER.debug(' - FOUND %d TASKS', len(_tasks))
        return _tasks

    def find_ver(self, match, catch=True, force=False, **kwargs):
        """Find version.

        Args:
            match (str): match version by name/path
            catch (bool): no error if no version found
            force (bool): force reread cached data

        Returns:
            (SGCVersion): matching version
        """
        _LOGGER.debug('FIND VER %s', match)
        _match_s = to_str(match)

        _vers = self.find_vers(force=force, **kwargs)
        if len(_vers) == 1:
            _ver = single(_vers)
            if not match or _apply_ver_match(match=match, version=_ver):
                return _ver

        _matches = [
            _ver for _ver in _vers
            if _apply_ver_match(match=match, version=_ver)]
        if len(_matches) == 1:
            return single(_matches)

        if catch:
            return None
        raise ValueError(match, kwargs)

    def find_vers(self, force=False, **kwargs):
        """Search versions in this entity.

        Args:
            force (bool): force reread cached data

        Returns:
            (SGCVer list): tasks
        """
        _LOGGER.debug('FIND TASKS %s', kwargs)
        _vers = []
        for _ver in self._read_vers(force=force):
            if not sgc_utils.passes_filters(_ver, **kwargs):
                continue
            _vers.append(_ver)
        _LOGGER.debug(' - FOUND %d VERS', len(_vers))
        return _vers

    @sg_cache_result
    def _read_pub_files(self, attempts=5, force=False):
        """Read pub files in this entity.

        Args:
            attempts (int): number of attempts to make before erroring
            force (bool): force reread from shotgrid

        Returns:
            (SGCPubFile list): pub files
        """
        _LOGGER.debug('READ PUB FILES %s', self)

        # Attempt to obtain shotgrid pub files data
        for _idx in range(attempts):

            _last_t = self._read_elems_updated_t(sgc_elems.SGCPubFile)
            if not _last_t:
                return []
            _LOGGER.debug(' - LAST T %s', strftime('nice', _last_t))

            _last_t_c, _pub_files_c = self._build_pub_files_cache(force=force)
            if _last_t_c != _last_t:
                _last_t_c, _pub_files_c = self._build_pub_files_cache(
                    force=True)
                _LOGGER.debug(
                    ' - T CMP last="%s" cache="%s"',
                    strftime('nice', _last_t),
                    strftime('nice', _last_t_c))
                if _last_t_c != _last_t:
                    _LOGGER.error(
                        f'SHOTGRID RETURNED BAD PUB FILES DATA {self} - '
                        f'ATTEMPT {_idx:d}/{attempts}')
                    time.sleep(1)
                    continue

            return _pub_files_c

        raise RuntimeError(
            f'Shotgrid returned bad pub files data {self}')

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

        _LOGGER.info('BUILD PUB FILES DATA force=%d %s', force, self)
        _LOGGER.debug(' - CACHE FMT %s', self.cache_fmt)

        # Read pub file elements
        _pub_files = self._read_elems(
            sgc_elems.SGCPubFile, force=force)
        assert _pub_files
        _LOGGER.debug(' - FOUND %d PUB FILES', len(_pub_files))
        _last_t = to_time_f(max(
            _pub_file.updated_at for _pub_file in _pub_files))

        # Validate output path
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
                _pub_file.task = _out.task

        _LOGGER.debug(' - COMPLETE')

        return _last_t, _pub_files

    def _read_tasks(self, force=False):
        """Read tasks inside this entity.

        Args:
            force (bool): force rebuild cached data

        Returns:
            (SGCTask list): tasks
        """
        return self._read_elems(sgc_elems.SGCTask, force=force)

    def _read_vers(self, force=False):
        """Read vers inside this entity.

        Args:
            force (bool): force rebuild cached data

        Returns:
            (SGCTask list): vers
        """
        return self._read_elems(sgc_elems.SGCVersion, force=force)

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
        'sg_head_in', 'code', 'sg_sequence', 'sg_status_list', 'assets',
        'updated_at', 'sg_has_3d', 'project', 'sg_tail_out', 'sg_overscan')

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


def _apply_ver_match(match, version):
    """Apply test whether the given version matches.

    Args:
        match (any): object to match to
        version (SGCVersion): version to match with

    Returns:
        (bool): whether version is the same as match in terms of
            name or path or object
    """
    _match_s = to_str(match)
    return (
        match in (version, ) or
        _match_s in (version.path, version.name))
