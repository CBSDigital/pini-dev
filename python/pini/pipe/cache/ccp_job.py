"""Tools for managing the cacheable job object."""

import functools
import logging
import operator
import time

import six

from pini.utils import single, apply_filter, get_method_to_file_cacher

from .ccp_utils import pipe_cache_result
from ..cp_job import CPJob
from ..cp_entity import CPEntity

_LOGGER = logging.getLogger(__name__)


class CCPJob(CPJob):  # pylint: disable=too-many-public-methods
    """Caching version of the CPJob object."""

    def __init__(self, path, cache, **kwargs):
        """Constructor.

        Args:
            path (str): path within job
            cache (CPCache): parent cache
        """
        self.cache = cache
        super(CCPJob, self).__init__(path, **kwargs)

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
        _rel_path = '.pini/cache/{}/{{func}}.pkl'.format(self.cfg['name'])
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

    @property
    def work_dirs(self):
        """Obtain list of work dirs in this job.

        NOTE: this is only applicable to shotgrid jobs.

        Returns:
            (CCPWorkDir tuple): work dirs
        """
        return tuple(self._read_work_dirs_sg())

    @property
    def outputs(self):
        """Obtain list of outputs in this job.

        NOTE: this is only applicable to shotgrid jobs.

        Returns:
            (CCPWorkDir tuple): outputs
        """
        return tuple(self._read_outputs_sg())

    @pipe_cache_result
    def find_asset_types(self, force=False):
        """Search for asset types in this job.

        Args:
            force (bool): force reread asset types from disk

        Returns:
            (str list): asset types
        """
        return super(CCPJob, self).find_asset_types()

    @functools.wraps(CPJob.create)
    def create(self, *args, **kwargs):
        """Create this job.

        Returns:
            (CCPJob): updated job
        """
        _LOGGER.debug('CREATE JOB %s', self)
        super(CCPJob, self).create(*args, **kwargs)
        assert self.exists()
        self.cache.find_jobs(force=True)
        _LOGGER.debug(' - JOBS %s', self.cache.jobs)
        assert self in self.cache.jobs
        _job = self.cache.find_job(self)
        return _job

    def find_assets(self, asset_type=None, filter_=None, force=False):
        """Find assets in this job.

        Args:
            asset_type (str): filter by asset type
            filter_ (str): filter by path
            force (bool): force reread assets list from disk

        Returns:
            (CCPAsset list): matching assets
        """
        from pini import pipe
        _LOGGER.debug('FIND ASSETS force=%d', force)

        if pipe.MASTER == 'disk':
            _types = [asset_type] if asset_type else self.asset_types
            _LOGGER.debug(' - TYPES %s', _types)
            _assets = []
            for _type in _types:
                _type_assets = self.read_type_assets(
                    asset_type=_type, force=force)
                _LOGGER.debug(' - FOUND type=%s %s', _type, _type_assets)
                _assets += _type_assets
        elif pipe.MASTER == 'shotgrid':
            if force:
                self._read_assets_sg(force=True)
            _assets = super(CCPJob, self).find_assets(
                asset_type=asset_type)
        else:
            raise ValueError(pipe.MASTER)

        if filter_:
            _assets = apply_filter(
                _assets, filter_, key=operator.attrgetter('path'))

        return _assets

    @pipe_cache_result
    def _read_assets_disk_natd(self, class_=None, force=False):
        """Read assets from disk (no asset type dirs).

        NOTE: only applicable to jobs where asset type dirs are not used.

        Args:
            class_ (class): override asset class
            force (bool): force reread from disk
        """
        from .ccp_entity import CCPAsset
        _LOGGER.debug('READ ASSETS')
        return super(CCPJob, self)._read_assets_disk_natd(
            class_=class_ or CCPAsset)

    @pipe_cache_result
    def _read_assets_sg(self, class_=None, force=False):
        """Read assets from shotgrid.

        Args:
            class_ (class): override asset class
            force (bool): force reread from disk
        """
        from .ccp_entity import CCPAsset
        _LOGGER.debug('READ ASSETS')
        return super(CCPJob, self)._read_assets_sg(class_=class_ or CCPAsset)

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
        from .ccp_entity import CCPAsset
        _LOGGER.debug('READ TYPE ASSETS %s force=%d',
                      asset_type, force)
        if not self.uses_sequence_dirs and force:
            self._read_assets_disk_natd(force=True)
        _assets = super(CCPJob, self).read_type_assets(
            asset_type=asset_type, class_=class_ or CCPAsset)
        _LOGGER.debug(' - FOUND %d ASSETS %s', len(_assets), _assets)
        return _assets

    @functools.wraps(CPJob.find_publishes)
    def find_publishes(self, force=False, **kwargs):
        """Find asset publishes within this job.

        Args:
            force (bool): force build asset publish disk caches

        Returns:
            (CPOutput list): publishes
        """
        if force:
            from pini import qt, pipe
            if pipe.MASTER == 'disk':
                for _asset in qt.progress_bar(
                        self.assets, 'Reading {:d} asset{}'):
                    _asset.find_publishes(force=True)
            elif pipe.MASTER == 'shotgrid':
                self._read_outputs_sg(force=True)
            else:
                raise ValueError(pipe.MASTER)

        return super(CCPJob, self).find_publishes(**kwargs)

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
        return super(CCPJob, self).find_sequence(match)

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
        from .ccp_entity import CCPSequence
        return super(CCPJob, self).find_sequences(
            class_=class_ or CCPSequence, filter_=filter_, head=head)

    def find_shot(self, *args, **kwargs):
        """Find a shot in this job.

        Returns:
            (CCPShot): matching shot
        """
        _force = kwargs.pop('force', False)
        if _force:
            self.find_shots(force=True)
        return super(CCPJob, self).find_shot(*args, **kwargs)

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
        _LOGGER.debug('FIND SHOTS')
        if force:
            if not self.uses_sequence_dirs:
                self._read_shots_disk(force=True)
            elif sequence:
                sequence.find_shots(force=True)

        return super(CCPJob, self).find_shots(
            sequence=sequence, class_=class_, filter_=filter_)

    @pipe_cache_result
    def _read_shots_disk(self, class_=None, force=False):
        """Read shots from disk.

        (Only applicable to jobs where sequence dirs are not used)

        Args:
            class_ (class): override shot class
            force (bool): force reread from disk
        """
        from .ccp_entity import CCPShot
        _LOGGER.debug('READ SHOTS force=%d', force)
        return super(CCPJob, self)._read_shots_disk(class_=class_ or CCPShot)

    @pipe_cache_result
    def read_shots_sg(self, class_=None, force=False):
        """Read shots from shotgrid.

        Args:
            class_ (class): override shot class
            force (bool): force reread shots from disk

        Returns:
            (CCPShot list): shots
        """
        from .ccp_entity import CCPShot
        _LOGGER.debug('READ SHOTS force=%d', force)
        return super(CCPJob, self).read_shots_sg(class_=class_ or CCPShot)

    @pipe_cache_result
    def obt_entity(self, match):
        """Obtain entity an entity in this job.

        Args:
            match (str|CPEntity): token to match with entity

        Returns:
            (CCPEntity): matching entity
        """
        from pini import pipe
        _LOGGER.debug('FIND ENTITY %s', match)

        _match = match
        if isinstance(_match, six.string_types):
            _ety = pipe.to_entity(_match)
            if _ety:
                _match = _ety
                _LOGGER.debug(' - MAPPED TO ENTITY %s', _match)

        if isinstance(_match, six.string_types):
            _LOGGER.debug(' - STR MATCH %s', _match)
            _matches = [_ety for _ety in self.entities
                        if _ety.name == _match]
            _LOGGER.debug(' - STR MATCHES %s', _matches)
            return single(_matches)

        if isinstance(_match, CPEntity):
            _etys = self.entities
            _LOGGER.debug(' - ETYS %s', _etys)
            _matches = [_ety for _ety in _etys if _ety == _match]
            _LOGGER.debug(' - ETY MATCHES %s', _matches)
            return single(_matches, catch=True)

        return super(CCPJob, self).find_entity(_match)

    def obt_work_dir(self, match):
        """Obtain a work dir object within this job.

        Args:
            match (CPWorkDir): work dir to match

        Returns:
            (CCPWorkDir): cached work dir
        """
        from pini import pipe
        if isinstance(match, pipe.CPWorkDir):
            if pipe.MASTER == 'shotgrid':
                _work_dirs = self._read_work_dirs_sg()
                _result = single([
                    _work_dir for _work_dir in _work_dirs
                    if _work_dir == match])
            else:
                raise NotImplementedError(pipe.MASTER)
            return _result

        raise NotImplementedError(match)

    def find_work_dirs(self, entity=None, force=False):
        """Find work dirs within this job.

        NOTE: this is only applicable to shotgrid jobs, where work dirs
        are cached at job level.

        Args:
            entity (CPEntity): entity filter
            force (bool): rebuild cache

        Returns:
            (CCPWorkDir list): work dirs
        """
        from pini import pipe
        assert pipe.MASTER == 'shotgrid'
        _work_dirs = []
        for _work_dir in self._read_work_dirs_sg(force=force):
            if entity and _work_dir.entity != entity:
                continue
            _work_dirs.append(_work_dir)
        return _work_dirs

    @pipe_cache_result
    def _read_work_dirs_sg(self, force=False):
        """Read work dirs in this job from shotgrid.

        Args:
            force (bool): rebuild cache

        Returns:
            (CCPWorkDir list): work dirs
        """
        _LOGGER.debug('READ WORK DIRS SG %s', self)
        from pini.pipe import shotgrid, cache

        _start = time.time()
        _sg = shotgrid.to_handler()
        _tmpl = self.find_template('work_dir')
        _LOGGER.debug(' - TMPL %s', _tmpl)

        # Build entity map
        _etys = self.entities
        _LOGGER.debug(' - FOUND %d ETYS', len(_etys))
        _e_start = time.time()
        _ety_map = {}
        for _ety in reversed(_etys):
            _key = _ety.profile, shotgrid.to_entity_id(_ety)
            _ety_map[_key] = _ety
        _LOGGER.debug(' - MAPPED %d ETYS IN %.01fs', len(_ety_map),
                      time.time() - _e_start)

        # Read tasks from shotgrid
        _s_start = time.time()
        if self.entities:
            _filters = [
                shotgrid.to_job_filter(self),
                shotgrid.to_entities_filter(self.entities)]
            _results = _sg.find(
                'Task', filters=_filters,
                fields=shotgrid.TASK_FIELDS+['entity'])
        else:
            _results = []
        _LOGGER.debug(' - FOUND %d RESULTS IN %.01fs', len(_results),
                      time.time() - _s_start)

        # Map tasks to work dirs
        _work_dirs = []
        for _idx, _result in enumerate(_results):

            _task = _result['sg_short_name']
            if not _result['step'] or not _task:
                continue

            # Find entity
            _LOGGER.debug(
                '[%d/%d] TESTING %s %s', _idx, len(_results),
                _result['entity']['name'], _result['sg_short_name'])
            _ety_data = _result['entity']
            _ety_type = _ety_data['type']
            if _ety_type in ['Sequence']:
                _LOGGER.debug(' - REJECTING TYPE %s', _ety_type)
                continue
            _ety_key = _ety_data['type'].lower(), _ety_data['id']
            _LOGGER.debug(' - ETY KEY %s', _ety_key)
            if _ety_key not in _ety_map:
                continue
            _ety = _ety_map[_ety_key]
            _LOGGER.debug(' - ETY %s', _ety)

            # Obtain step data
            _step_data = shotgrid.to_step_data(_result['step']['id'])
            _LOGGER.debug(' - STEP DATA %s', _step_data)
            _step = _step_data['short_name']
            _LOGGER.debug(' - STEP/TASK %s %s', _step, _task)

            # Build path
            _path = _tmpl.format(
                entity_path=_ety.path, step=_step, task=_task)
            _LOGGER.debug(' - PATH %s', _path)

            _work_dir = cache.CCPWorkDir(_path, entity=_ety)
            _work_dirs.append(_work_dir)

        _LOGGER.debug(
            'FOUND %d WORK DIRS (%.01fs)', len(_work_dirs),
            time.time() - _start)
        return _work_dirs

    def find_outputs(self, *args, **kwargs):
        """Find outputs in this job.

        Args:
            force (bool): force reread outputs

        Returns:
            (CPOutput list): outputs
        """
        _kwargs = kwargs
        _force = _kwargs.pop('force', False)
        if _force:
            self._read_outputs_sg(force=True)
        return super(CCPJob, self).find_outputs(*args, **_kwargs)

    @pipe_cache_result
    def _read_outputs_sg(self, force=False):
        """Read outputs in this job from shotgrid.

        Args:
            force (bool): force reread outputs

        Returns:
            (CCPOutput list): outputs
        """
        from pini import pipe
        from pini.pipe import cache

        assert pipe.MASTER == 'shotgrid'
        _outs = self._read_sg_pub_files(force=force)

        # Convert to cacheable objects
        _c_outs = []
        for _out in _outs:

            _LOGGER.debug(' - ADD OUT %s', _out)

            # Find entity
            _ety = self.obt_entity(_out.entity)
            if not _ety:
                continue

            # Find work dir
            _work_dir = None
            if _out.work_dir:
                _work_dir = _ety.obt_work_dir(_out.work_dir)

            # Build output object
            _kwargs = {
                'entity': _ety,
                'work_dir': _work_dir,
            }
            if isinstance(_out, pipe.CPOutputVideo):
                _c_out = cache.CCPOutputVideo(_out, **_kwargs)
            elif isinstance(_out, pipe.CPOutput):
                _c_out = cache.CCPOutput(_out, **_kwargs)
            elif isinstance(_out, pipe.CPOutputSeq):
                _c_out = cache.CCPOutputSeq(_out.path, **_kwargs)
            else:
                raise ValueError(_out)

            _LOGGER.debug('   - C OUT %s', _c_out)
            _c_outs.append(_c_out)

        return _c_outs

    @get_method_to_file_cacher(max_age=60*60*24)
    def _read_sg_pub_files(self, force=False):
        """Read shotgrid published files for this job.

        Args:
            force (bool): force re-read cache

        Returns:
            (CPOutput list): outputs
        """
        from pini.pipe import shotgrid
        _outs = shotgrid.find_pub_files(job=self, entities=self.entities)
        return _outs

    @pipe_cache_result
    def to_prefix(self):
        """Obtain prefix for this job.

        Returns:
            (str): job prefix
        """
        return super(CCPJob, self).to_prefix()

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
        from .ccp_entity import CCPAsset
        return super(CCPJob, self).to_asset(
            asset_type, asset, class_=class_ or CCPAsset, catch=catch)

    def to_sequence(self, sequence, class_=None, catch=False):
        """Build a sequence object for this job.

        Args:
            sequence (CPSequence): sequence name
            class_ (class): override sequence class
            catch (bool): no error if no valid sequence created

        Returns:
            (CPSequence): sequence
        """
        from .ccp_entity import CCPSequence
        return super(CCPJob, self).to_sequence(
            sequence, class_=class_ or CCPSequence, catch=catch)

    def to_shot(self, shot, sequence=None, class_=None):
        """Build a shot object based on the given args.

        Args:
            shot (str): shot name
            sequence (str): sequence
            class_ (class): override shot type

        Returns:
            (CPShot): shot object
        """
        from .ccp_entity import CCPShot
        return super(CCPJob, self).to_shot(
            sequence=sequence, shot=shot, class_=class_ or CCPShot)

    def create_asset_type(self, *args, **kwargs):
        """Create a new asset type in this job.

        Args:
            asset_type (str): asset type name
            force (bool): create without confirmation dialog
        """
        super(CCPJob, self).create_asset_type(*args, **kwargs)
        self.find_asset_types(force=True)
