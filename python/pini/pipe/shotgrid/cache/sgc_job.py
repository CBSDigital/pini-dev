"""Tools for managing jobs in the shotgrid cache."""

# pylint: disable=too-many-instance-attributes

import logging
import operator
import pprint
import time

from pini import pipe, qt
from pini.pipe.cache import pipe_cache_on_obj
from pini.utils import (
    single, strftime, to_time_f, check_heart, Path, basic_repr,
    passes_filter, to_str)

from . import sgc_range, sgc_container, sgc_utils

_LOGGER = logging.getLogger(__name__)


class SGCJob(sgc_container.SGCContainer):
    """Represents a job on shotgrid."""

    def __init__(self, data, cache, job):
        """Constructor.

        Args:
            data (dict): job shotgrid data
            cache (SGDataCache): parent cache
            job (CPJob): pipe job object
        """
        super(SGCJob, self).__init__(data)

        self.cache = cache
        self.job = job

        self.sg = cache.sg

        self.prefix = data['sg_short_name']
        self.name = data['tank_name']
        self.path = data['path']

        self.filter_ = ('project', 'is', self.to_entry())
        if not self.name:
            raise ValueError(data)

        self.root = pipe.JOBS_ROOT.to_subdir(self.name)

    @property
    def assets(self):
        """Obtain list of assets in this job.

        Returns:
            (SGCAsset list): assets
        """
        return self._read_assets()

    @property
    def entities(self):
        """Obtain list of entities in this job.

        Returns:
            (SGCAsset|SGCShot list): assets + shots
        """
        return self.assets + self.shots

    @property
    def pub_files(self):
        """Obtain list of published files in this job.

        Returns:
            (SGCPubFile list): pub files
        """
        return self._read_pub_files()

    @property
    def shots(self):
        """Obtain list of shot in this job.

        Returns:
            (SGCShot list): shots
        """
        return self._read_shots()

    @property
    def tasks(self):
        """Obtain list of tasks in this job.

        Returns:
            (SGCTask list): tasks
        """
        return self._read_tasks()

    def find_asset(self, match):
        """Find asset within this job.

        Args:
            match (str): asset name/path

        Returns:
            (SGCAsset): matching asset
        """
        return single([
            _asset for _asset in self.assets
            if match in (_asset.name, _asset.path)])

    def find_assets(self, progress=False, force=False):
        """Search assets within this job.

        Args:
            progress (bool): show read progress
            force (bool): force reread data

        Returns:
            (SGCAsset list): assets
        """
        return self._read_assets(progress=progress, force=force)

    def find_entity(self, match):
        """Find entity within this job.

        Args:
            match (str|CPEntity): entity or path to match

        Returns:
            (SGCAsset|SGCShot): matching entity
        """
        _match_s = to_str(match)
        return single([
            _ety for _ety in self.entities
            if _match_s in (_ety.name, _ety.path)])

    def find_pub_file(self, path=None):
        """Find a pub file in this job.

        Args:
            path (str): match by path

        Returns:
            (SGCPubFile): matching pub file
        """
        _path = to_str(path)
        for _pub_file in self.pub_files:
            if _pub_file.path == _path:
                return _pub_file
        raise ValueError(path)

    def find_pub_files(
            self, entity=None, work_dir=None, progress=False, force=False):
        """Search pub file within this job.

        Args:
            entity (CPEntity): filter by entity
            work_dir (CPWorkDir): filter by work dir
            progress (bool): show read progress
            force (bool): force reread data

        Returns:
            (SGCPubFile list): pub files
        """
        _pubs = []
        for _pub in self._read_pub_files(progress=progress, force=force):
            if entity and not entity.contains(_pub.path):
                continue
            if work_dir and not work_dir.contains(_pub.path):
                continue
            _pubs.append(_pub)
        return _pubs

    def find_shot(self, match=None, filter_=None):
        """Find shot in this job.

        Args:
            match (str): match by name/path
            filter_ (str): apply shot name filter

        Returns:
            (SGCShot): matching shot
        """
        _shots = self.find_shots(filter_=filter_)

        if len(_shots) == 1:
            return single(_shots)

        _match_shots = [
            _shot for _shot in _shots if match in (_shot.name, _shot.path)]
        if len(_match_shots):
            return single(_match_shots)

        raise ValueError(match, filter_)

    def find_shots(
            self, has_3d=None, filter_=None, progress=False, force=False):
        """Search shots within this job.

        Args:
            has_3d (bool): filter by has 3d status
            filter_ (str): apply shot name filter
            progress (bool): show read progress
            force (bool): force reread data

        Returns:
            (SGCShot list): shots
        """
        _shots = []
        for _shot in self._read_shots(progress=progress, force=force):
            if has_3d is not None and _shot.has_3d != has_3d:
                continue
            if filter_ and not passes_filter(_shot.name, filter_):
                continue
            _shots.append(_shot)
        return _shots

    def find_task(self, path=None, entity=None, task=None, step=None):
        """Find task within this job.

        Args:
            path (str): match by path
            entity (CPEntity): filter by entity
            task (str): filter by task
            step (str): filter by step

        Returns:
            (SGCTask): matching task
        """
        _tasks = self.find_tasks(entity=entity, task=task, step=step)
        if len(_tasks) == 1:
            return single(_tasks)
        for _task in _tasks:
            if _task.path == path:
                return _task
        raise ValueError(path, entity, task, step)

    def find_tasks(
            self, entity=None, task=None, step=None, department=None,
            filter_=None, progress=False, force=False):
        """Search tasks within this job.

        Args:
            entity (CPEntity): filter by entity
            task (str): filter by task
            step (str): filter by step
            department (str): filter by department (eg. 3D/2D)
            filter_ (str): apply step/task name filter
            progress (bool): show read progress
            force (bool): force reread data

        Returns:
            (SGCTask list): tasks
        """

        # Prepare steps data
        _steps = set()
        if step:
            _steps |= set(self.cache.find_steps(short_name=step))
        if department:
            _steps |= set(self.cache.find_steps(department='3d'))
        _step_ids = {_step.id_ for _step in _steps}
        _step_map = {_step.id_: _step.short_name for _step in self.cache.steps}

        _tasks = []
        for _task in self._read_tasks(progress=progress, force=force):

            if entity and not entity.contains(_task.path):
                continue
            if task and _task.name != task:
                continue
            if _step_ids and _task.step_id not in _step_ids:
                continue

            if filter_:
                if not passes_filter(_task.name, filter_):
                    continue
                _full_task = '{}/{}'.format(
                    _step_map[_task.step_id], _task.name)
                if not passes_filter(_full_task, filter_):
                    continue

            _tasks.append(_task)
        return _tasks

    def _read_data(
            self, entity_type, fields, entity_map=None, ver_n=None,
            use_snapshots=True, progress=False, force=False):
        """Read data from shotgrid.

        If the data hasn't been updated since it was last read, the cached
        result is used. Otherwise the cache is rebuilt from date ranges.

        Args:
            entity_type (str): entity type to read
            fields (str list): fields to read
            entity_map (dict): map of profile/id keys with entity values
            ver_n (int): apply version number suffix to cache file
            use_snapshots (bool): use timestamped snapshots
            progress (bool): show read progress
            force (bool): force reread data
                1 - rebuild cache from date ranges
                2 - reread all data from shotgrid

        Returns:
            (dict list): shotgrid results
        """
        _LOGGER.debug('FIND %s IN %s', entity_type, self.name)

        _last_t = self._read_last_t(entity_type=entity_type)
        _last_rng = sgc_range.SGCRange(_last_t, period='D')
        _snapshot = sgc_utils.to_cache_file(
            entity_type=entity_type, job=self, fields=fields,
            range_=_last_rng, ver_n=ver_n)
        _LOGGER.debug(' - SNAPSHOT %s', _snapshot)

        _results = None
        if use_snapshots and not force and _snapshot.exists():
            try:
                _results = _snapshot.read_pkl()
            except EOFError:
                _LOGGER.info(' - FAILED TO READ SNAPSHOT %s', self.path)

        if _results is None:
            _LOGGER.info(
                ' - BUILDING CACHE %d %s %s %s',
                force, self.job.name, entity_type, _snapshot.path)
            _results = self._read_data_from_ranges(
                entity_type=entity_type, fields=fields, entity_map=entity_map,
                progress=progress, ver_n=ver_n, force=force > 1)
            _snapshot.write_pkl(_results, force=True)

        return sorted(_results, key=operator.itemgetter('path'))

    def _read_data_from_ranges(
            self, entity_type, fields, entity_map=None, ver_n=None,
            progress=False, force=False):
        """Read shotgrid data from time range buckets.

        Args:
            entity_type (str): entity type to read
            fields (str list): fields to read
            entity_map (dict): map of profile/id keys with entity values
            ver_n (int): apply version number suffix to cache file
            progress (bool): show read progress
            force (bool): force reread data from shotgrid

        Returns:
            (dict list): shotgrid results
        """
        _first_t = self._read_first_t(
            entity_type=entity_type, force=force)
        _ranges = sgc_range.build_ranges(start_t=_first_t)

        # Read + validate data
        _v_start = time.time()
        _path_map = {}
        for _rng in qt.progress_bar(
                _ranges,
                '[SGC] Checking {} {}'.format(self.name, entity_type),
                stack_key='SGCReadRanges', show=progress, col='Orange'):

            _LOGGER.debug(_rng.label)
            _cache_file = sgc_utils.to_cache_file(
                entity_type=entity_type, fields=fields, job=self, range_=_rng,
                ver_n=ver_n)

            # Obtain results
            if not force and _cache_file and _cache_file.exists():
                _r_results = _cache_file.read_pkl()
            else:
                _r_results = self._read_data_from_range(
                    range_=_rng, entity_type=entity_type, fields=fields,
                    entity_map=entity_map, progress=progress)
                if _cache_file:
                    _cache_file.write_pkl(_r_results, force=True)

            # Add results to path map to filter old results
            for _result in _r_results:
                _path_map[_result['path']] = _result

        _results = list(_path_map.values())
        _LOGGER.debug(
            ' - FOUND %d RESULTS IN %.01fs', len(_results),
            time.time() - _v_start)

        return _results

    def _read_data_from_range(
            self, range_, entity_type, fields, entity_map, progress):
        """Read shotgrid data from the given time range,.

        Args:
            range_ (SGCRange): time range
            entity_type (str): entity type to read
            fields (str list): fields to read
            entity_map (dict): map of profile/id keys with entity values
            progress (bool): show read progress

        Returns:
            (dict list): shotgrid results
        """
        _r_results = []
        _sg_results = self.sg.find(
            entity_type,
            filters=[
                self.filter_,
                ('updated_at', 'between', range_.to_tuple()),
            ],
            order=[{'field_name': 'updated_at', 'direction': 'asc'}],
            fields=fields)

        for _result in qt.progress_bar(
                _sg_results,
                '[SGC] Reading {} {} results ({{:d}})'.format(
                    range_.label, entity_type),
                show=progress, col='Yellow',
                stack_key='SGCValidateResults'):

            check_heart()
            _LOGGER.debug(' - RESULT %s', _result)

            # Determine step short name
            _step = None
            if 'step' in _result:
                if not _result['step']:
                    continue
                _step_id = _result['step']['id']
                if not _step_id:
                    continue
                _step = self.cache.find_step(_step_id).short_name

            # Validate result by obtaining pipe object
            _path = _path_from_result(
                result=_result, entity_type=entity_type, job=self.job,
                step=_step, entity_map=entity_map)
            if not _path:
                continue

            # Add path data to result
            if isinstance(_path, pipe.CPOutputBase):
                _result['has_work_dir'] = bool(_path.work_dir)
            _result['path'] = _path.path
            _result['template'] = _path.template.source.pattern
            _result['template_type'] = _path.template.type_

            _r_results.append(_result)

        return _r_results

    def _read_create_t(self):
        """Obtain creation time for this job.

        Returns:
            (float): creation time
        """
        return to_time_f(self.data['created_at'])

    def _read_first_t(self, entity_type, force=False):
        """Read and cache the first time this data type was updated.

        Args:
            entity_type (str): entity type to read
            force (bool): force reread shotgrid

        Returns:
            (float): first update time
        """
        _cache_file = self.root.to_file(
            '.pini/sgc/first_{}.pkl'.format(entity_type))
        _LOGGER.debug(' - CACHE FILE %s', _cache_file)
        if not force and _cache_file.exists():
            _first_t = _cache_file.read_pkl()
        else:
            _results = self.sg.find(
                entity_type,
                filters=[self.filter_],
                fields=['updated_at'],
                limit=1,
                order=[{'field_name': 'updated_at', 'direction': 'asc'}])
            if _results:
                _first = single(_results)
                _first_t = to_time_f(_first['updated_at'])
            else:
                _first_t = time.time()
            _cache_file.write_pkl(_first_t, force=True)

        _LOGGER.debug(
            ' - FIRST %s %s', entity_type, strftime('%d/%m/%y', _first_t))

        return _first_t

    def _read_last_t(self, entity_type):
        """Read time for last update of given data type.

        Args:
            entity_type (str): entity type to read

        Returns:
            (float): last update time
        """
        _results = self.sg.find(
            entity_type,
            filters=[self.filter_],
            fields=['updated_at'],
            limit=1,
            order=[{'field_name': 'updated_at', 'direction': 'desc'}])
        if not _results:
            return self._read_create_t()
        return single(_results)['updated_at']

    @pipe_cache_on_obj
    def _read_assets(self, progress=False, force=False):
        """Build list of assets in this job.

        Args:
            progress (bool): show read progress
            force (bool): force rebuild cache

        Returns:
            (SGCAsset list): assets
        """
        _fields = ['sg_asset_type', 'code', 'sg_status_list', 'updated_at']
        _data = self._read_data(
            entity_type='Asset', fields=_fields, progress=progress,
            force=force)
        _assets = []
        for _item in _data:
            _asset = sgc_container.SGCAsset(_item)
            _assets.append(_asset)
        return _assets

    @pipe_cache_on_obj
    def _read_pub_files(self, progress=True, force=False):
        """Build list of pub files in this job.

        Args:
            progress (bool): show read progress
            force (bool): force rebuild cache

        Returns:
            (SGCPubFile list): pub files
        """
        _fields = [
            'path_cache', 'path', 'sg_status_list', 'updated_at', 'updated_by']
        _data = self._read_data(
            entity_type='PublishedFile', fields=_fields, progress=progress,
            ver_n=2, force=force)
        _pub_files = []
        for _item in _data:
            _pub_file = sgc_container.SGCPubFile(_item)
            _pub_files.append(_pub_file)
        return _pub_files

    @pipe_cache_on_obj
    def _read_shots(self, progress=False, force=False):
        """Build list of shots in this job.

        Args:
            progress (bool): show read progress
            force (bool): force rebuild cache

        Returns:
            (SGCShot list): shots
        """
        _fields = [
            'sg_head_in', 'code', 'sg_sequence', 'sg_status_list',
            'updated_at', 'sg_has_3d']
        _data = self._read_data(
            entity_type='Shot',
            fields=_fields,
            progress=progress, force=force)
        _shots = []
        for _item in _data:
            _shot = sgc_container.SGCShot(_item)
            _shots.append(_shot)
        return _shots

    @pipe_cache_on_obj
    def _read_tasks(self, progress=True, force=False):
        """Build list of tasks in this job.

        Args:
            progress (bool): show read progress
            force (bool): force rebuild cache

        Returns:
            (SGCTask list): tasks
        """
        _fields = [
            'step', 'sg_short_name', 'entity', 'sg_status_list', 'updated_at']
        _ety_map = {(_ety.type_, _ety.id_): _ety for _ety in self.entities}
        _data = self._read_data(
            entity_type='Task', entity_map=_ety_map, fields=_fields,
            progress=progress, force=force)
        _tasks = []
        for _item in _data:
            _task = sgc_container.SGCTask(_item)
            if _task.status in ('omt', ):
                continue
            _tasks.append(_task)
        return _tasks

    @pipe_cache_on_obj
    def to_cache_dir(self):
        """Obtain shotgrid root cache directory for this job.

        Returns:
            (Dir): cache dir
        """
        return self.job.to_subdir('.pini/sgc/'+self.job.cfg['name'])

    def __lt__(self, other):
        return self.name.lower() < other.name.lower()

    def __repr__(self):
        return basic_repr(self, self.name)


def _path_from_result(result, entity_type, job, step=None, entity_map=None):
    """Build a pipe path object from the given shotgrid result.

    Args:
        result (dict): shotgrid result
        entity_type (str): entity type
        job (CPJob): parent job
        step (str): step name
        entity_map (dict): entity map

    Returns:
        (CPAsset|CPShot|CPWorkFile|CPOutput): pipe path object
    """
    check_heart()
    assert isinstance(job, pipe.CPJob)

    if entity_type == 'Asset':
        _path = job.to_subdir('assets/{}/{}'.format(
            result['sg_asset_type'], result['code']))
        _asset = pipe.CPAsset(_path, job=job)
        return _asset

    if entity_type == 'Shot':
        _seq_data = result.get('sg_sequence', {}) or {}
        _seq_name = _seq_data.get('name')
        _path = job.to_subdir('episodes/{}/{}'.format(
            _seq_name, result['code']))
        try:
            _shot = pipe.CPShot(_path, job=job)
        except ValueError:
            return None
        return _shot

    if entity_type == 'Task':
        return _work_dir_from_result(
            result, step=step, entity_map=entity_map, job=job)

    if entity_type == 'PublishedFile':
        return _output_from_result(
            result, job=job)

    _LOGGER.info('VALIDATE %s %s', entity_type, result)
    pprint.pprint(result)
    raise NotImplementedError


def _output_from_result(result, job):
    """Build output object from the given shotgrid result.

    Args:
        result (dict): shotgrid result
        job (CPJob): parent job

    Returns:
        (CPOutput): output
    """
    _path = result.get('path_cache')
    if _path and not Path(_path).is_abs():
        _path = pipe.JOBS_ROOT.to_file(_path)
    if not _path:
        _path_dict = result.get('path') or {}
        _path = _path_dict.get('local_path')
    if not _path:
        return None
    _LOGGER.debug(' - PATH %s', _path)
    if not job.contains(_path):
        return None
    _out = pipe.to_output(_path, catch=True)
    return _out


def _work_dir_from_result(result, step, entity_map, job):
    """Build work dir object from the given shotgrid result.

    Args:
        result (dict): shotgrid result
        step (str): step name
        entity_map (dict): entity map
        job (CPJob): parent job

    Returns:
        (CPWorkDir): work dir
    """
    _LOGGER.debug('VALIDATE TASK %s', result)

    # Obtain entity path
    assert entity_map is not None
    if 'entity' not in result or not result['entity']:
        return None
    _ety_id = result['entity']['id']
    _ety_type = result['entity']['type']
    _ety_name = result['entity']['name']
    if _ety_type in ('Sequence', 'CustomEntity01'):
        return None
    if _ety_name.endswith(' (Copy)'):
        return None
    assert isinstance(_ety_id, int)
    _LOGGER.debug(' - ENTITY %s %s', _ety_id, _ety_type)

    _key = _ety_type, _ety_id
    if _key not in entity_map:
        return None
    _ety = entity_map[_key]

    assert step
    _task = result['sg_short_name']
    if not _task:
        return None
    _tmpl = job.find_template('work_dir', profile=_ety_type.lower())
    _LOGGER.debug(' - TMPL %s', _tmpl)
    _path = _tmpl.format(
        entity_path=_ety.path, step=step, task=_task)
    _LOGGER.debug(' - PATH %s', _path)
    _ety = pipe.to_entity(_path, job=job)

    return pipe.CPWorkDir(_path, entity=_ety)
