"""Tools for managing jobs in the shotgrid cache."""

# pylint: disable=too-many-instance-attributes

import logging

from pini import pipe
from pini.utils import single, basic_repr, passes_filter, to_str

from ...cache import pipe_cache_on_obj
from . import sgc_elem, sgc_ety, sgc_utils

_LOGGER = logging.getLogger(__name__)


class SGCProj(sgc_elem.SGCElem):
    """Represents a job on shotgrid."""

    ENTITY_TYPE = 'Project'
    FIELDS = (
        'updated_at', 'tank_name', 'sg_short_name', 'sg_frame_rate',
        'sg_status', 'created_at')
    STATUS_KEY = 'sg_status'

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
        _LOGGER.debug('FIND ASSET %s', match)
        _entity_type = _name = None
        if isinstance(match, pipe.CPEntity):
            _entity_type = match.entity_type
            _name = match.name
            _LOGGER.debug(' - TYPE/ETY %s %s', _entity_type, _name)

        _assets = self.find_assets(
            filter_=filter_, entity_type=_entity_type, name=_name)
        if len(_assets) == 1:
            return single(_assets)
        _LOGGER.debug(' - MATCHED %d ASSETS', len(_assets))

        return single([
            _asset for _asset in _assets
            if match in (_asset.name, _asset.uid, _asset.id_)])

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

    def find_entity(self, match=None, catch=False, **kwargs):
        """Find entity within this job.

        Args:
            match (str|CPEntity|CPOutput): entity or path to match
            catch (bool): no error if fail to match entity

        Returns:
            (SGCAsset|SGCShot): matching entity
        """
        _LOGGER.debug('FIND ENTITY %s %s', match, kwargs)

        _ety = None
        if isinstance(match, pipe.CPEntity):
            _ety = match
        elif isinstance(match, pipe.CPOutputBase):
            _ety = match.entity
        if not _ety:
            _ety = pipe.to_entity(match, catch=True)

        # Build search kwargs
        _kwargs = kwargs
        if _ety:
            _kwargs['name'] = _kwargs.get(
                'name', _ety.name)
            _kwargs['entity_type'] = _kwargs.get(
                'entity_type', _ety.entity_type)
        _LOGGER.debug(' - FIND ENTITES %s', _kwargs)

        # Find matching entities
        _etys = self.find_entities(**_kwargs)
        if len(_etys) == 1:
            return single(_etys)
        _LOGGER.debug(' - MATCHED %d ETYS', len(_etys))

        # Attempt string match
        _match_s = to_str(match)
        _LOGGER.debug(' - MATCH_S %s', _match_s)
        _match_etys = [
            _ety for _ety in self.entities
            if _match_s in (_ety.name, )]
        _LOGGER.debug(' - MATCH ETYS %d %s', len(_match_etys), _match_etys)
        if len(_match_etys) == 1:
            return single(_match_etys)

        if catch:
            return None
        raise ValueError(match, _kwargs)

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

    def find_shot(self, match=None, filter_=None, catch=False):
        """Find shot in this job.

        Args:
            match (str): match by name/path
            filter_ (str): apply shot name filter
            catch (bool): no error if fail to find shot

        Returns:
            (SGCShot): matching shot
        """
        _entity_type = _name = None
        if isinstance(match, pipe.CPEntity):
            _entity_type = match.entity_type
            _name = match.name

        _LOGGER.debug('FIND SHOT %s', match)
        _shots = self.find_shots(
            filter_=filter_, entity_type=_entity_type, name=_name)
        _match_s = to_str(match)
        _LOGGER.debug(' - MATCH_S %s', _match_s)

        if len(_shots) == 1:
            return single(_shots)

        _match_shots = [
            _shot for _shot in _shots
            if _match_s in (_shot.name, _shot.uid)]
        if len(_match_shots):
            return single(_match_shots)

        if catch:
            return None
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
        return self.job.to_subdir('.pini/sgc/' + self.job.cfg['name'])

    def __lt__(self, other):
        return self.name.lower() < other.name.lower()

    def __repr__(self):
        return basic_repr(self, self.name)
