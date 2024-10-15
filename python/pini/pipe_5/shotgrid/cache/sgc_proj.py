"""Tools for managing jobs in the shotgrid cache."""

# pylint: disable=too-many-instance-attributes

import logging

from pini import pipe
from pini.utils import single, basic_repr, passes_filter, to_str

from ...cache import pipe_cache_on_obj
from . import sgc_container, sgc_ety, sgc_utils

_LOGGER = logging.getLogger(__name__)


class SGCProj(sgc_container.SGCContainer):
    """Represents a job on shotgrid."""

    ENTITY_TYPE = 'Project'
    FIELDS = (
        'updated_at', 'tank_name', 'sg_short_name', 'sg_frame_rate',
        'sg_status', 'created_at')

    def __init__(self, data):
        """Constructor.

        Args:
            data (dict): job shotgrid data
        """
        super().__init__(data)

        # self.cache = cache
        self.job = None

        self.prefix = data['sg_short_name']
        self.name = data['tank_name']

        self.filter_ = ('project', 'is', self.to_entry())
        if not self.name:
            raise ValueError('Missing name')

        self.path = pipe.ROOT.to_subdir(self.name).path

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
    def shots(self):
        """Obtain list of shot in this job.

        Returns:
            (SGCShot list): shots
        """
        return self._read_shots()

    def find_asset(self, match=None, filter_=None):
        """Find asset within this job.

        Args:
            match (str): asset name/path
            filter_ (str): apply path filter

        Returns:
            (SGCAsset): matching asset
        """
        _assets = self.find_assets(filter_=filter_)
        if len(_assets) == 1:
            return single(_assets)

        return single([
            _asset for _asset in _assets
            if match in (_asset.name, _asset.uid)])

    def find_assets(self, filter_=None, force=False, **kwargs):
        """Search assets within this job.

        Args:
            filter_ (str): apply path filter
            force (bool): force reread data

        Returns:
            (SGCAsset list): assets
        """
        _assets = []
        for _asset in self._read_assets(force=force):
            if filter_ and not passes_filter(_asset.uid, filter_):
                continue
            if not sgc_utils.passes_filters(_asset, **kwargs):
                continue
            _assets.append(_asset)
        return _assets

    def find_entity(self, match=None, **kwargs):
        """Find entity within this job.

        Args:
            match (str|CPEntity): entity or path to match
            id_ (int): apply id filter
            type_ (str): apply element type filter

        Returns:
            (SGCAsset|SGCShot): matching entity
        """
        _kwargs = kwargs
        _LOGGER.debug('FIND ENTITY %s %s', match, _kwargs)

        if isinstance(match, pipe.CPEntity):
            _kwargs['name'] = _kwargs.get(
                'name', match.name)
            _kwargs['entity_type'] = _kwargs.get(
                'entity_type', match.entity_type)
        _LOGGER.debug(' - FIND ENTITES %s', _kwargs)
        
        _etys = self.find_entities(**_kwargs)
        if len(_etys) == 1:
            return single(_etys)
        _LOGGER.debug(' - MATCHED %d ETYS', len(_etys))

        _match_s = to_str(match)
        _LOGGER.debug(' - MATCH_S %s', _match_s)

        _match_etys = [
            _ety for _ety in self.entities
            if _match_s in (_ety.name, )]
        _LOGGER.debug(' - MATCH ETYS %d %s', len(_match_etys), _match_etys)
        if len(_match_etys) == 1:
            return single(_match_etys)

        _contains_etys = [
            _ety for _ety in self.entities
            if _match_s.startswith(_ety.path)]
        if len(_contains_etys) == 1:
            return single(_contains_etys)

        raise ValueError(match)

    def find_entities(self, type_=None, force=False, **kwargs):
        """Search entities in this project.

        Args:
            type_ (str): apply element type filter
            force (bool): reread cached data

        Returns:
            (SGCAsset|SGCShot list): matching entities
        """
        _etys = []
        if type_ not in (None, 'Asset', 'Shot'):
            raise ValueError(type_)
        if type_ in (None, 'Asset'):
            _etys += self.find_assets(force=force, **kwargs)
        if type_ in (None, 'Shot'):
            _etys += self.find_shots(force=force, **kwargs)
        return _etys

    def find_shot(self, match=None, filter_=None):
        """Find shot in this job.

        Args:
            match (str): match by name/path
            filter_ (str): apply shot name filter

        Returns:
            (SGCShot): matching shot
        """
        _LOGGER.debug('FIND SHOT %s', match)
        _shots = self.find_shots(filter_=filter_)
        _match_s = to_str(match)
        _LOGGER.debug(' - MATCH_S %s', _match_s)

        if len(_shots) == 1:
            return single(_shots)

        _match_shots = [
            _shot for _shot in _shots
            if _match_s in (_shot.name, _shot.uid)]
        if len(_match_shots):
            return single(_match_shots)

        raise ValueError(match, filter_)

    def find_shots(self, filter_=None, force=False, **kwargs):
        """Search shots within this job.

        Args:
            filter_ (str): apply shot name filter
            force (bool): force reread data

        Returns:
            (SGCShot list): shots
        """
        _shots = []
        for _shot in self._read_shots(force=force):
            if not sgc_utils.passes_filters(_shot, **kwargs):
                continue
            if filter_ and not passes_filter(_shot.name, filter_):
                continue
            _shots.append(_shot)
        return _shots

    @pipe_cache_on_obj
    def _read_assets(self, force=False):
        """Build list of assets in this job.

        Args:
            force (bool): force rebuild cache

        Returns:
            (SGCAsset list): assets
        """
        return self._read_elems(
            sgc_ety.SGCAsset, sort_attr='uid', force=force)

    @pipe_cache_on_obj
    def _read_shots(self, force=False):
        """Build list of shots in this job.

        Args:
            force (bool): force rebuild cache

        Returns:
            (SGCShot list): shots
        """
        return self._read_elems(
            sgc_ety.SGCShot, sort_attr='uid', force=force)

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


# def _path_from_result(  # pylint: disable=too-many-return-statements
#         result, entity_type, job, step=None, entity_map=None):
#     """Build a pipe path object from the given shotgrid result.

#     Args:
#         result (dict): shotgrid result
#         entity_type (str): entity type
#         job (CPJob): parent job
#         step (str): step name
#         entity_map (dict): entity map

#     Returns:
#         (CPAsset|CPShot|CPWorkFile|CPOutputFile): pipe path object
#     """
#     check_heart()
#     assert isinstance(job, pipe.CPJob)

#     if entity_type == 'Asset':
#         _path = job.to_subdir('assets/{}/{}'.format(
#             result['sg_asset_type'], result['code']))
#         _asset = pipe.CPAsset(_path, job=job)
#         return _asset

#     if entity_type == 'Shot':
#         _seq_data = result.get('sg_sequence', {}) or {}
#         _seq_name = _seq_data.get('name')
#         _path = job.to_subdir('episodes/{}/{}'.format(
#             _seq_name, result['code']))
#         try:
#             _shot = pipe.CPShot(_path, job=job)
#         except ValueError:
#             return None
#         return _shot

#     if entity_type == 'Task':
#         return _work_dir_from_result(
#             result, step=step, entity_map=entity_map, job=job)

#     if entity_type == 'PublishedFile':
#         return _output_from_result(result, job=job)

#     if entity_type == 'Version':
#         _mov_path = result['sg_path_to_movie']
#         if not _mov_path:
#             return None
#         _LOGGER.debug(' - MOV PATH %s', _mov_path)
#         return pipe.to_output(_mov_path, catch=True)

#     _LOGGER.info('VALIDATE %s %s', entity_type, result)
#     pprint.pprint(result)
#     raise NotImplementedError(entity_type)


# def _output_from_result(result, job):
#     """Build output object from the given shotgrid result.

#     Args:
#         result (dict): shotgrid result
#         job (CPJob): parent job

#     Returns:
#         (CPOutput): output
#     """
#     _path = result.get('path_cache')
#     if _path and not Path(_path).is_abs():
#         _path = pipe.ROOT.to_file(_path)
#     if not _path:
#         _path_dict = result.get('path') or {}
#         _path = _path_dict.get('local_path')
#     if not _path:
#         return None
#     _LOGGER.debug(' - PATH %s', _path)
#     if not job.contains(_path):
#         return None
#     _out = pipe.to_output(_path, catch=True)
#     return _out


# def _work_dir_from_result(result, step, entity_map, job):
#     """Build work dir object from the given shotgrid result.

#     Args:
#         result (dict): shotgrid result
#         step (str): step name
#         entity_map (dict): entity map
#         job (CPJob): parent job

#     Returns:
#         (CPWorkDir): work dir
#     """
#     _LOGGER.debug('VALIDATE TASK %s', result)

#     # Obtain entity path
#     assert entity_map is not None
#     if 'entity' not in result or not result['entity']:
#         return None
#     _ety_id = result['entity']['id']
#     _ety_type = result['entity']['type']
#     _ety_name = result['entity']['name']
#     if _ety_type in ('Sequence', 'CustomEntity01'):
#         return None
#     if _ety_name.endswith(' (Copy)'):
#         return None
#     assert isinstance(_ety_id, int)
#     _LOGGER.debug(' - ENTITY %s %s', _ety_id, _ety_type)

#     _key = _ety_type, _ety_id
#     if _key not in entity_map:
#         return None
#     _ety = entity_map[_key]

#     assert step
#     _task = result['sg_short_name']
#     if not _task:
#         return None
#     _tmpl = job.find_template('work_dir', profile=_ety_type.lower())
#     _LOGGER.debug(' - TMPL %s', _tmpl)
#     _path = _tmpl.format(
#         entity_path=_ety.path, step=step, task=_task)
#     _LOGGER.debug(' - PATH %s', _path)
#     _ety = pipe.to_entity(_path, job=job)

#     return pipe.CPWorkDir(_path, entity=_ety)
