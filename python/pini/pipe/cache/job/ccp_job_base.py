"""Tools for managing the cacheable job object."""

# pylint: disable=too-many-public-methods

import functools
import logging
import time

from pini import icons
from pini.utils import single, cache_method_to_file, str_to_seed

from ..ccp_utils import pipe_cache_result
from ...elem import CPJob, CPEntity

_LOGGER = logging.getLogger(__name__)


class CCPJobBase(CPJob):
    """Caching version of the CPJob object."""

    def __init__(self, path, cache, **kwargs):
        """Constructor.

        Args:
            path (str): path within job
            cache (CPCache): parent cache
        """
        self.cache = cache
        super().__init__(path, **kwargs)

    @property
    def asset_types(self):
        """Access the asset types list.

        Returns:
            (str list): asset types list
        """
        return tuple(self.find_asset_types())

    @property
    def assets(self):
        """Access the list of assets in this job.

        Returns:
            (CCPAsset tuple): assets
        """
        return tuple(self.find_assets())

    @property
    def cache_fmt(self):
        """Obtain cache path format for this job.

        Returns:
            (str): cache format
        """
        from pini import pipe
        _cfg_name = self.cfg['name']
        _ver = pipe.VERSION
        _rel_path = f'.pini/cache/P{_ver:d}_{_cfg_name}/{{func}}.pkl'
        return self.to_file(_rel_path).path

    @property
    def publishes(self):
        """Obtain list of publishes in this job.

        Returns:
            (CCPOutput list): publishes
        """
        return tuple(self.find_publishes())

    @property
    def sequences(self):
        """Access the list of sequences in this job.

        Returns:
            (str tuple): sequences
        """
        return tuple(self.find_sequences())

    @property
    def shots(self):
        """Access the list of shots in this job.

        Returns:
            (CCPShot tuple): shots
        """
        return tuple(self.find_shots())

    @property
    def entities(self):
        """Obtain list of all entities in this job.

        Returns:
            (CCPEntity tuple): entities
        """
        return tuple(self.find_assets() + self.find_shots())

    @pipe_cache_result
    def find_asset_types(self, force=False):
        """Search for asset types in this job.

        Args:
            force (bool): force reread asset types from disk

        Returns:
            (str list): asset types
        """
        return super().find_asset_types()

    @functools.wraps(CPJob.create)
    def create(self, *args, **kwargs):
        """Create this job.

        Returns:
            (CCPJob): updated job
        """
        _LOGGER.debug('CREATE JOB %s', self)
        super().create(*args, **kwargs)
        assert self.exists()
        self.cache.find_jobs(force=True)
        _LOGGER.debug(' - JOBS %s', self.cache.jobs)
        assert self in self.cache.jobs
        _job = self.cache.find_job(self)
        return _job

    @cache_method_to_file
    def ctime(self):
        """Obtain create time for this job.

        Returns:
            (float): create time
        """
        return super().ctime()

    @pipe_cache_result
    def read_type_assets(self, asset_type, class_=None, force=False):
        """Read assets of the given type.

        Args:
            asset_type (str): asset type to read
            class_ (class): force asset class
            force (bool): force reread from disk

        Returns:
            (CCPAsset list): matching assets
        """
        from ... import cache
        _LOGGER.debug('READ TYPE ASSETS %s force=%d',
                      asset_type, force)
        _assets = super().read_type_assets(
            asset_type=asset_type, class_=class_ or cache.CCPAsset)
        _LOGGER.debug(' - FOUND %d ASSETS %s', len(_assets), _assets)
        return _assets

    def find_publish(self, match=None, **kwargs):
        """Find a publish within this job.

        Args:
            match (str): match by path/name

        Returns:
            (CPOutputGhost): matching publish
        """
        _pubs = self.find_publishes(**kwargs)
        if len(_pubs) == 1:
            return single(_pubs)
        _LOGGER.info(
            ' - KWARGS MATCHED %d %s %s', len(_pubs), _pubs[:5],
            '...' if len(_pubs) > 5 else '')

        _matches = [_pub for _pub in _pubs if match in (_pub.path, )]
        if len(_matches) == 1:
            return single(_matches)

        raise ValueError(match or kwargs)

    def find_publishes(self, task=None, entity=None, force=False, **kwargs):
        """Find asset publishes within this job.

        Args:
            task (str): filter by task
            entity (CPEntity): filter by entity
            force (bool): force rebuild publishes cache

        Returns:
            (CPOutputGhost list): publishes
        """
        from pini import pipe
        _LOGGER.debug('FIND PUBLISHES')
        _start = time.time()
        _pubs = []
        for _pub in self._read_publishes(force=force):
            if entity and (
                    _pub.asset_type != entity.asset_type or
                    _pub.asset != entity.asset or
                    _pub.sequence != entity.sequence or
                    _pub.shot != entity.shot):
                continue
            if not pipe.passes_filters(_pub, task=task, **kwargs):
                continue
            _pubs.append(_pub)
        _LOGGER.debug('FOUND %s %d PUBLISHES IN %.01fs', self, len(_pubs),
                      time.time() - _start)
        return _pubs

    def _read_publishes(self, force=False):
        """Read publishes in this job.

        Args:
            force (bool): force rebuild disk cache

        Returns:
            (CPOutputGhost list): publishes
        """
        raise NotImplementedError

    @pipe_cache_result
    def obt_sequence(self, match):
        """Obtain a matching sequence in this job.

        Args:
            match (any): sequence to match

        Returns:
            (CCPSequence): matching sequence
        """
        from pini import pipe
        if isinstance(match, pipe.CPSequence):
            return single([_seq for _seq in self.sequences if _seq == match])
        return super().find_sequence(match)

    @pipe_cache_result
    def find_sequences(self, class_=None, filter_=None, head=None, force=False):
        """Find sequences in this job.

        Args:
            class_ (CPSequence): override sequence class
            filter_ (str): filter by name
            head (str): filter by sequence name prefix
            force (bool): force reread from disk

        Returns:
            (str list): sequences
        """
        from ... import cache
        return super().find_sequences(
            class_=class_ or cache.CCPSequence, filter_=filter_, head=head)

    def find_shot(self, *args, **kwargs):
        """Find a shot in this job.

        Returns:
            (CCPShot): matching shot
        """
        _force = kwargs.pop('force', False)
        if _force:
            self.find_shots(force=True)
        return super().find_shot(*args, **kwargs)

    def find_shots(self, sequence=None, class_=None, filter_=None, force=False):
        """Find shots in this job.

        Args:
            sequence (str): filter by sequence
            class_ (class): override shot class
            filter_ (str): filter by shot name
            force (bool): force reread from disk

        Returns:
            (CPShot list): matching shots
        """
        _LOGGER.log(9, 'FIND SHOTS')
        if force and sequence:
            sequence.find_shots(force=True)

        return super().find_shots(
            sequence=sequence, class_=class_, filter_=filter_)

    @pipe_cache_result
    def obt_entity(self, match):
        """Obtain entity an entity in this job.

        Args:
            match (str|CPEntity): token to match with entity

        Returns:
            (CCPEntity): matching entity
        """
        from pini import pipe
        _LOGGER.log(9, 'FIND ENTITY %s', match)

        _match = match
        if isinstance(_match, str):
            _ety = pipe.to_entity(_match)
            if _ety:
                _match = _ety
                _LOGGER.debug(' - MAPPED TO ENTITY %s', _match)

        if isinstance(_match, str):
            _LOGGER.debug(' - STR MATCH %s', _match)
            _matches = [_ety for _ety in self.entities
                        if _ety.name == _match]
            _LOGGER.debug(' - STR MATCHES %s', _matches)
            return single(_matches)

        if isinstance(_match, CPEntity):
            _etys = self.entities
            _LOGGER.log(9, ' - ETYS %s', _etys)
            _matches = [_ety for _ety in _etys if _ety == _match]
            _LOGGER.log(9, ' - ETY MATCHES %s', _matches)
            return single(_matches, catch=True)

        return super().find_entity(_match)

    def obt_work_dir(self, match, catch=False):
        """Obtain a work dir object within this job.

        Args:
            match (CPWorkDir): work dir to match
            catch (bool): no error if fail to find work dir

        Returns:
            (CCPWorkDir): cached work dir
        """
        raise NotImplementedError

    def find_works(self, **kwargs):
        """Find work files in this job.

        Returns:
            (CCPWork list): works
        """
        _works = []
        for _ety in self.entities:
            _works += _ety.find_works(**kwargs)
        return _works

    def find_outputs(self, **kwargs):
        """Find outputs in this job.

        Returns:
            (CCPOutput list): outputs
        """
        _outs = []
        for _ety in self.entities:
            _outs += _ety.find_outputs(**kwargs)
        return _outs

    def to_asset(self, asset_type, asset, class_=None, catch=True):
        """Build an asset object for an asset within this job.

        Args:
            asset_type (str): asset type
            asset (str): asset name
            class_ (class): override asset class
            catch (bool): no error if fail to build valid asset

        Returns:
            (CCPAsset): asset object
        """
        from ... import cache
        return super().to_asset(
            asset_type, asset, class_=class_ or cache.CCPAsset, catch=catch)

    def to_sequence(self, sequence, class_=None, catch=False):
        """Build a sequence object for this job.

        Args:
            sequence (CPSequence): sequence name
            class_ (class): override sequence class
            catch (bool): no error if no valid sequence created

        Returns:
            (CPSequence): sequence
        """
        from ... import cache
        return super().to_sequence(
            sequence, class_=class_ or cache.CCPSequence, catch=catch)

    def to_shot(self, shot, sequence=None, class_=None):
        """Build a shot object based on the given args.

        Args:
            shot (str): shot name
            sequence (str): sequence
            class_ (class): override shot type

        Returns:
            (CPShot): shot object
        """
        from ... import cache
        return super().to_shot(
            sequence=sequence, shot=shot, class_=class_ or cache.CCPShot)

    def to_col(self):
        """Obtain colour for this job.

        Returns:
            (QColor): job colour
        """
        from pini import qt
        _rand = str_to_seed(self.name)
        if self.settings['col']:
            _col = self.settings['col']
        else:
            _col = _rand.choice(qt.BOLD_COLS)
            _col = qt.CColor(_col)
            _col = _col.whiten(0.2)
        return _col

    def to_icon(self):
        """Obtain icon for this job.

        Returns:
            (str): path to icon
        """
        from pini import testing
        _rand = str_to_seed(self.name)

        # Add icon
        if self.settings['icon']:
            _icon = icons.find(self.settings['icon'])
        elif self == testing.TEST_JOB:
            _icon = icons.find('Alembic')
        elif 'Library' in self.name:
            _icon = icons.find('Books')
        else:
            _icon = _rand.choice(icons.FRUIT)

        return _icon

    def create_asset_type(self, *args, **kwargs):
        """Create a new asset type in this job.

        Args:
            asset_type (str): asset type name
            force (bool): create without confirmation dialog
        """
        super().create_asset_type(*args, **kwargs)
        self.find_asset_types(force=True)
