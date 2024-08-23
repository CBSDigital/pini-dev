"""Tools for managing the cacheable job object."""

import functools
import logging
import operator
import os

import six

from pini.utils import (
    single, apply_filter, get_method_to_file_cacher, cache_method_to_file,
    check_heart)

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
        return tuple(self.find_work_dirs())

    @property
    def outputs(self):
        """Obtain list of outputs in this job.

        NOTE: this is only applicable to shotgrid jobs.

        Returns:
            (CCPWorkDir tuple): outputs
        """
        return tuple(self.find_outputs())

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

    @cache_method_to_file
    def ctime(self):
        """Obtain create time for this job.

        Returns:
            (float): create time
        """
        return super(CCPJob, self).ctime()

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
        _LOGGER.log(9, 'FIND ASSETS force=%d', force)

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
        _LOGGER.log(9, 'FIND SHOTS')
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
    def read_shots_sg(self, class_=None, filter_=None, force=False):
        """Read shots from shotgrid.

        Args:
            class_ (class): override shot class
            filter_ (str): apply name filter
            force (bool): force reread shots from disk

        Returns:
            (CCPShot list): shots
        """
        from .ccp_entity import CCPShot
        if filter_:
            raise RuntimeError('Filter not allowed to maintain cache integrity')
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
        _LOGGER.log(9, 'FIND ENTITY %s', match)

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
            _LOGGER.log(9, ' - ETYS %s', _etys)
            _matches = [_ety for _ety in _etys if _ety == _match]
            _LOGGER.log(9, ' - ETY MATCHES %s', _matches)
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
                _matches = [
                    _work_dir for _work_dir in _work_dirs
                    if _work_dir == match]
                _result = single(
                    _matches, error='Failed to match {}'.format(match))
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

        _etys = list(self.entities)
        _work_dirs = []
        _filter = os.environ.get('PINI_PIPE_TASK_FILTER')
        for _sg_task in shotgrid.SGC.find_tasks(
                job=self, department='3d', filter_=_filter):

            _LOGGER.debug(' - TASK %s', _sg_task)

            # Find entity
            _ety = _iter_to_next_parent(path=_sg_task.path, parents=_etys)
            _LOGGER.debug('   - ETY %s', _ety)
            if not _ety:
                continue

            _work_dir = cache.CCPWorkDir(_sg_task.path, entity=_ety)
            _work_dirs.append(_work_dir)

        return _work_dirs

    def find_outputs(  # pylint: disable=arguments-differ
            self, type_=None, content_type=None, force=False, progress=False,
            **kwargs):
        """Find outputs in this job.

        Args:
            type_ (str): filter by output type
            content_type (str): filter by content type (eg. ShadersMa, Render)
            force (bool): force reread outputs
            progress (bool): show progress dialog

        Returns:
            (CPOutput list): outputs
        """
        from pini import qt
        _LOGGER.debug(
            'FIND OUTPUTS type=%s force=%d progress=%d', type_, force, progress)

        if force:
            self._read_outputs_sg(force=True, progress=progress)

        _outs = []
        _all_outs = super(CCPJob, self).find_outputs(type_=type_, **kwargs)
        for _out in qt.progress_bar(
                _all_outs, 'Checking {:d} output{}', show=progress):
            if content_type and _out.content_type != content_type:
                continue
            _outs.append(_out)
        return _outs

    @pipe_cache_result
    def _read_outputs_sg(self, progress=False, force=False):
        """Read outputs in this job from shotgrid.

        Args:
            progress (bool): show progress dialog
            force (bool): force reread outputs

        Returns:
            (CCPOutput list): outputs
        """
        _LOGGER.debug('READ OUTPUTS SG %s', self)
        from pini import pipe
        from pini.pipe import cache, shotgrid

        _etys = list(self.entities)
        _work_dirs = list(self.work_dirs)

        _outs = []
        for _sg_pub in shotgrid.SGC.find_pub_files(job=self, force=force):

            _LOGGER.debug('PUB %s', _sg_pub)
            if _sg_pub.status in ('omt', ):
                continue

            # Find parent entity or work dir
            _work_dir = _ety = None
            if not _sg_pub.has_work_dir:
                _ety = _iter_to_next_parent(
                    path=_sg_pub.path, parents=_etys)
            else:
                _work_dir = _iter_to_next_parent(
                    path=_sg_pub.path, parents=_work_dirs)
            if not (_ety or _work_dir):
                continue
            _LOGGER.debug(' - ETY %s', _ety)
            _LOGGER.debug(' - WORK DIR %s', _work_dir)

            # Determine output class
            if _sg_pub.template_type in pipe.OUTPUT_FILE_TYPES:
                _class = cache.CCPOutput
            elif _sg_pub.template_type in pipe.OUTPUT_VIDEO_TYPES:
                _class = cache.CCPOutputVideo
            elif _sg_pub.template_type in pipe.OUTPUT_SEQ_TYPES:
                _class = cache.CCPOutputSeq
            else:
                raise ValueError(_sg_pub.template_type)

            # Build output object
            _tmpl = self.find_template_by_pattern(_sg_pub.template)
            try:
                _out = _class(
                    _sg_pub.path, entity=_ety, work_dir=_work_dir,
                    template=_tmpl, latest=_sg_pub.latest)
            except ValueError:  # Can fail if config changed
                _LOGGER.warning(' - BUILD OUT FAILED %s', _sg_pub)
                continue
            _LOGGER.debug('   - OUT %s', _out)

            _outs.append(_out)
            assert isinstance(_out.entity, cache.CCPEntity)

        return _outs

    @get_method_to_file_cacher()
    def get_sg_output_template_map(self, map_=None, force=False):
        """Get shotgrid output template map.

        This maps paths to their output template pattern, and is used to
        streamline build output objects from shotgrid results, by avoiding
        each result needing to be checked against a full list output
        templates.

        Args:
            map_ (dict): output template map to apply to cache
            force (bool): force write result to disk

        Returns:
            (dict): output template map
        """
        return map_ or {}

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


def _iter_to_next_parent(path, parents):
    """Iterate the given order list to find the next parent.

    eg. Iterate over a sorted list of shots to find the shot containing the
    given path. If the path provided falls before (alphabetically) the next
    shot, it's assumed that the path doesn't fall within a shot and None
    is returned.

    NOTE: the list of parents is altered during this process

    Args:
        path (str): path to iterate to
        parents (Dir list): ordered list of parents

    Returns:
        (Dir|None): next parent dir (if any)
    """
    _parent = None
    while parents:
        check_heart()
        if parents[0].contains(path):
            _parent = parents[0]
            break
        if parents[0].path > path:
            _LOGGER.debug('   - PARENT NOT FOUND')
            break
        _LOGGER.debug('   - MOVING TO NEXT PARENT %s', parents[0])
        parents.pop(0)

    if _parent:
        assert _parent.contains(path)

    return _parent
