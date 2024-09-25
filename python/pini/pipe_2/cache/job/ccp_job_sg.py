"""Tools for managing cacheable jobs on a sg-based pipeline."""

# pylint: disable=no-member

import logging
import operator
import os
import time

from pini import qt
from pini.utils import (
    single, apply_filter, get_method_to_file_cacher, check_heart)

from ..ccp_utils import pipe_cache_result, pipe_cache_to_file
from . import ccp_job_base

_LOGGER = logging.getLogger(__name__)


class CCPJobSG(ccp_job_base.CCPJobBase):
    """Represents a cacheable job on a sg-based pipeline."""

    @property
    def outputs(self):
        """Obtain list of outputs in this job.

        NOTE: this is only applicable to shotgrid jobs.

        Returns:
            (CCPWorkDir tuple): outputs
        """
        return tuple(self.find_outputs())

    @property
    def work_dirs(self):
        """Obtain list of work dirs in this job.

        Returns:
            (CCPWorkDir tuple): work dirs
        """
        return tuple(self.find_work_dirs())

    @pipe_cache_result
    def to_prefix(self):
        """Obtain prefix for this job.

        Returns:
            (str): job prefix
        """
        return super().to_prefix()

    def find_assets(self, asset_type=None, filter_=None, force=False):
        """Find assets in this job.

        Args:
            asset_type (str): filter by asset type
            filter_ (str): filter by path
            force (bool): force reread assets list from disk

        Returns:
            (CCPAsset list): matching assets
        """
        _LOGGER.log(9, 'FIND ASSETS force=%d', force)

        if force:
            self._read_assets(force=True)
        _assets = super().find_assets(asset_type=asset_type)

        if filter_:
            _assets = apply_filter(
                _assets, filter_, key=operator.attrgetter('path'))

        return _assets

    @pipe_cache_result
    def _read_assets(self, class_=None, force=False):
        """Read assets from shotgrid.

        Args:
            class_ (class): override asset class
            force (bool): force reread from disk
        """
        from ... import cache
        _LOGGER.debug('READ ASSETS')
        return super()._read_assets(class_=class_ or cache.CCPAsset)

    @pipe_cache_result
    def read_shots(self, class_=None, filter_=None, force=False):
        """Read shots from shotgrid.

        Args:
            class_ (class): override shot class
            filter_ (str): apply name filter
            force (bool): force reread shots from disk

        Returns:
            (CCPShot list): shots
        """
        from ... import cache
        if filter_:
            raise RuntimeError('Filter not allowed to maintain cache integrity')
        _LOGGER.debug('READ SHOTS force=%d', force)
        return super().read_shots(class_=class_ or cache.CCPShot)

    def find_outputs(
            self, type_=None, progress=True, force=False, **kwargs):
        """Find outputs in this job.

        (Only applicable to shotgrid jobs)

        Args:
            type_ (str): filter by output type
            progress (bool): show progress
            force (bool): force rebuild cache

        Returns:
            (CPOutput list): outputs
        """
        from pini import pipe
        _LOGGER.debug('FIND OUTPUTS %s', self)

        if force:
            self._read_outputs(force=True, progress=progress)

        _all_outs = self._read_outputs(progress=progress)
        _outs = []
        for _out in _all_outs:
            _LOGGER.debug(' - TESTING %s', _out)
            if not pipe.passes_filters(_out, type_=type_, **kwargs):
                continue
            _outs.append(_out)

        _LOGGER.debug(' - FOUND %d OUTPUTS', len(_outs))
        return sorted(_outs)

    @pipe_cache_result
    def _read_outputs(self, progress=True, force=False):
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
        for _sg_pub in shotgrid.SGC.find_pub_files(
                job=self, force=force, progress=progress):

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
                _class = cache.CCPOutputFile
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

    @pipe_cache_to_file
    def _read_publishes(self, force=False):
        """Read publishes in this job.

        Args:
            force (bool): force rebuild disk cache

        Returns:
            (CPOutputGhost list): publishes
        """
        _LOGGER.info('READING PUBLISHES %s', self)
        from pini import pipe

        # Find list of ouputs + streams
        _start = time.time()
        _streams = {}
        _to_add = []
        _outs = self.find_outputs()
        for _out in qt.progress_bar(
                _outs, 'Checking {:d} output{}',
                stack_key='ReadPublishes'):
            check_heart()
            if isinstance(_out, (pipe.CPOutputSeq, pipe.CPOutputVideo)):
                continue
            if _out.entity.profile != 'asset':
                continue
            _LOGGER.debug('OUT %s', _out)
            _stream = _out.to_stream()
            _to_add.append((_out, _stream))
            _streams[_stream] = _out
        _out_dur = time.time() - _start
        _LOGGER.info(' - CHECKED %d OUTPUTS IN %.01fs', len(_outs), _out_dur)

        # Build list of ghost publishes
        _pubs = []
        for _out, _stream in _to_add:
            _latest = _streams[_stream] == _out
            _pub = _out.to_ghost()
            _LOGGER.debug('   - PUB %s', _pub)
            _pubs.append(_pub)
        _pub_dur = time.time()
        _LOGGER.info(' - FOUND %d PUBS', len(_pubs))

        return _pubs

    def obt_work_dir(self, match, catch=False):
        """Obtain a work dir object within this job.

        Args:
            match (CPWorkDir): work dir to match
            catch (bool): no error if fail to find work dir

        Returns:
            (CCPWorkDir): cached work dir
        """
        from pini import pipe
        if isinstance(match, pipe.CPWorkDir):
            _work_dirs = self._read_work_dirs()
            _matches = [
                _work_dir for _work_dir in _work_dirs
                if _work_dir == match]
            _result = single(
                _matches, error='Failed to match {}'.format(match),
                catch=catch)
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
        _work_dirs = []
        for _work_dir in self._read_work_dirs(force=force):
            if entity and _work_dir.entity != entity:
                continue
            _work_dirs.append(_work_dir)
        return _work_dirs

    @pipe_cache_result
    def _read_work_dirs(self, force=False):
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
