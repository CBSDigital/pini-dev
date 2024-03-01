"""Tools for managing the pipeline cache.

This is a version of the pipeline api that caches key components
so that they're only read once. This object can be used to speed
up pipeline traversal in tools and avoid reread data that's used
more than once.

These cacheable objects can be distinguished from the generic pipeline
objects as their types have CCP prefix, rather than just CP.
"""

import logging
import operator
import time

import six

from pini.utils import (
    single, passes_filter, Dir, nice_age, norm_path, Path, flush_caches,
    apply_filter)

from ..cp_job import find_jobs, CPJob, cur_job
from ..cp_entity import cur_entity, to_entity
from ..cp_asset import cur_asset
from ..cp_shot import cur_shot
from ..cp_work_dir import CPWorkDir
from ..cp_work import CPWork, to_work
from ..cp_output import to_output, CPOutputBase

from . import ccp_job
from .ccp_utils import pipe_cache_on_obj, pipe_cache_result
from .ccp_entity import CCPEntity
from .ccp_work_dir import CCPWorkDir

_LOGGER = logging.getLogger(__name__)


class CPCache(object):  # pylint: disable=too-many-public-methods
    """Base object for the pipeline cache.

    Used to store top-level information, eg. list of jobs.

    Also used to access cacheable versions of current work/entity etc.
    """

    def __init__(self, jobs_root=None):
        """Constructor.

        Args:
            jobs_root (str): override jobs root path
        """
        self.ctime = time.time()
        self.jobs_root = jobs_root

    @property
    def cur_entity(self):
        """Find the cur entity (if any).

        Returns:
            (CCPEntity): current entity
        """
        _ety = cur_entity(job=self.cur_job)
        if not _ety:
            return None
        return self.obt_entity(_ety)

    @property
    def cur_job(self):
        """Object the current job object.

        Returns:
            (CCPJob): current job
        """
        _LOGGER.debug('CUR JOB root=%s', self.jobs_root)
        _job = cur_job(jobs_root=self.jobs_root)
        if not _job:
            return None
        return self.obt_job(_job)

    @property
    def cur_asset(self):
        """Find the current asset (if any).

        Returns:
            (CCPAsset): current asset
        """
        _asset = cur_asset()
        if not _asset:
            return None
        return self.obt_entity(_asset)

    @property
    def cur_shot(self):
        """Find the current shot (if any).

        Returns:
            (CCPShot): current shot
        """
        _shot = cur_shot()
        if not _shot:
            return None
        return self.obt_entity(_shot)

    @property
    def cur_work_dir(self):
        """Obtain current work directory.

        Returns:
            (CCPWorkDir): work dir
        """
        from pini import pipe
        _work_dir = pipe.cur_work_dir(entity=self.cur_entity)
        if not _work_dir:
            return None
        return self.obt_work_dir(_work_dir)

    @property
    def cur_work(self):
        """Find the current work file (if any).

        Returns:
            (CCPWork): current work
        """
        from pini import pipe
        _LOGGER.debug('CUR WORK %s', self.cur_work_dir)
        _work = pipe.cur_work()
        if not _work:
            _LOGGER.debug(' - NO CUR WORK')
            return None
        _work_c = self.obt_work(_work)
        _LOGGER.debug(' - CUR WORK %s', _work_c)
        return _work_c

    @property
    def entities(self):
        """Obtain tuple of all current entities.

        Returns:
            (CCPEntity tuple): entities
        """
        return tuple(self.find_entities())

    @property
    def jobs(self):
        """Access the jobs list.

        Returns:
            (CCPJob shots): jobs
        """
        return tuple(self.find_jobs())

    @property
    def shots(self):
        """Obtain tuple of all current shots.

        Returns:
            (CCPShot tuple): shots
        """
        return tuple(sum([list(_job.shots) for _job in self.jobs], []))

    @pipe_cache_result
    def obt_job(self, match):
        """Obtain a cacheable version of the given job.

        Args:
            match (str): job name to match

        Returns:
            (CCPJob): matching job
        """
        _LOGGER.debug('FIND JOB %s', match)

        _match = match
        if isinstance(_match, CPJob):
            try:
                return single(_job for _job in self.jobs if _job == _match)
            except ValueError:
                raise ValueError(
                    'Job {} is missing from jobs list (maybe missing config '
                    'file?)'.format(_match.name))
        if isinstance(_match, Path):
            _match = _match.path

        if isinstance(_match, six.string_types):

            _match = norm_path(_match)
            _LOGGER.debug(' - STR MATCH %s', _match)

            if '/' in _match:
                _LOGGER.debug(' - MATCH AS PATH')
                _job = CPJob(_match)
                return self.obt_job(_job)

            _name_match = single(
                [_job for _job in self.jobs if _job.name == _match],
                catch=True)
            if _name_match:
                return _name_match

            _filter_match = single(
                [_job for _job in self.jobs if passes_filter(
                    _job.name, _match)],
                catch=True)
            if _filter_match:
                return _filter_match

        raise NotImplementedError(match)

    def find_job(self, match=None, filter_=None, name=None, catch=False):
        """Find a matching job in the cache.

        Args:
            match (str): match by name/path
            filter_ (str): job name filter
            name (str): match by name
            catch (bool): no error if no job found

        Returns:
            (CCPJob): job
        """
        _LOGGER.debug('FIND JOBS')
        _jobs = self.find_jobs(filter_=filter_)

        if len(_jobs) == 1:
            return single(_jobs)
        if name:
            return single(
                [_job for _job in _jobs if _job.name == name], catch=catch)

        # Try name/path match
        _match_jobs = [_job for _job in _jobs if match in (_job.name, _job)]
        if len(_match_jobs) == 1:
            return single(_match_jobs)
        _LOGGER.debug(' - MATCH JOBS %s', _match_jobs)

        # Try filter match
        _filter_jobs = apply_filter(
            _jobs, match, key=operator.attrgetter('name'))
        if len(_filter_jobs) == 1:
            return single(_filter_jobs)
        _LOGGER.debug(' - FILTER JOBS %s', _filter_jobs)

        _LOGGER.debug(' - JOBS %s', _jobs)
        if catch:
            return None
        raise ValueError(match)

    def find_jobs(self, filter_=None, cfg_name=None, force=False):
        """Find jobs on the current pipeline.

        Args:
            filter_ (str): filter by job name
            cfg_name (str): filter by config name (eg. Acis/Satan/Pluto)
            force (bool): force reread from disk

        Returns:
            (CCPJob list): jobs
        """
        _jobs = []
        for _job in self._read_jobs(force=force):
            if not passes_filter(_job.name, filter_):
                continue
            if cfg_name and _job.cfg['name'] != cfg_name:
                continue
            _jobs.append(_job)
        return _jobs

    @pipe_cache_on_obj
    def _read_jobs(self, class_=None, force=False):
        """Find valid jobs on the current server.

        Args:
            class_ (class): override job class
            force (bool): force reread jobs from disk

        Returns:
            (CCPJob list): list of jobs
        """
        _LOGGER.debug('FIND JOBS %s', self.jobs_root)
        _class = class_ or ccp_job.CCPJob
        _jobs = find_jobs(jobs_root=self.jobs_root)
        _LOGGER.debug(' - JOBS %d %s', len(_jobs), _jobs)
        _c_jobs = [
            _class(path=_job.path, cache=self, jobs_root=self.jobs_root)
            for _job in _jobs
            if _job.cfg_file.exists(catch=True)]
        _LOGGER.debug(' - C JOBS %d %s', len(_c_jobs), _c_jobs)
        return _c_jobs

    def find_entities(self, filter_=None):
        """Find all entites in the pipeline.

        Args:
            filter_ (str): apply path filter

        Returns:
            (CCPEntity list): matching entites
        """
        return sum(
            [_job.find_entities(filter_=filter_) for _job in self.jobs], [])

    def to_job(self, name):
        """Obtain a job object matching the given name.

        If there's no existing job, a new job object is created.

        Args:
            name (str): job name

        Returns:
            (CCPJob): job object
        """
        _existing = single(
            [_job for _job in self.jobs if _job.name == name], catch=True)
        if _existing:
            return _existing
        _path = Dir(self.jobs_root).to_subdir(name)
        return ccp_job.CCPJob(path=_path, cache=self, jobs_root=self.jobs_root)

    def obt(self, obj):
        """Obtain the cache representation of the given object.

        Args:
            obj (any): pipeline object to retrieve from cache

        Returns:
            (any): cache representation
        """
        from pini import pipe
        if isinstance(obj, pipe.CPJob):
            return self.obt_job(obj)
        if isinstance(obj, (pipe.CPAsset, pipe.CPShot)):
            return self.obt_entity(obj)
        if isinstance(obj, pipe.CPWork):
            return self.obt_work(obj)
        raise NotImplementedError(obj)

    def obt_sequence(self, match):
        """Find a sequence object.

        Args:
            match (CPSequence): sequence to match

        Returns:
            (CCPSequence): matching sequence from cache
        """
        from pini import pipe
        if isinstance(match, pipe.CPSequence):
            _job = self.obt_job(match.job)
            return _job.obt_sequence(match)
        raise ValueError(match)

    @pipe_cache_result
    def obt_entity(self, match):
        """Find the given entity.

        Args:
            match (str|CPEntity|CPWork): token to match with entity

        Returns:
            (CCPEntity): matching entity
        """
        from pini import pipe
        _LOGGER.debug('FIND ENTITY %s', match)

        _match = match
        if isinstance(_match, (pipe.CPShot, pipe.CPAsset)):
            _LOGGER.debug(' - MATCH IS ENTITY')
            _job = self.obt_job(_match.job)
            _LOGGER.debug(' - USING JOB %s', _job)
            _ety = _job.obt_entity(_match)
            _LOGGER.debug(' - ETY %s', _ety)
            return _ety
        if isinstance(_match, (pipe.CPWork, pipe.CPOutputBase)):
            return self.obt_entity(_match.entity)

        if isinstance(_match, Path):
            _match = _match.path
        if isinstance(_match, six.string_types):
            _match = norm_path(_match)
            _LOGGER.debug(' - STR MATCH %s', _match)
            if _match.count('/') == 1:
                _job_name, _ety_name = _match.split('/')
                _job = self.obt_job(_job_name)
                return _job.obt_entity(_ety_name)
            if _match.count('/'):
                _ety = to_entity(_match)
                _LOGGER.debug(' - ENTITY %s', _ety)
                assert _ety
                _job = self.obt_job(_ety.job.name)
                assert isinstance(_job, ccp_job.CCPJob)
                return _job.obt_entity(_ety)

        raise NotImplementedError(match)

    def obt_work_dir(self, match):
        """Find the given work dir object.

        Args:
            match (any): work dir to match

        Returns:
            (CCPWorkDir): matching work dir
        """
        from pini import pipe

        _LOGGER.debug('FIND WORK DIR %s', match)
        _match = match

        # Located work dir to match
        if not isinstance(_match, CPWorkDir) and isinstance(_match, Path):
            _match = _match.path
            _LOGGER.debug(' - CONVERTED MATCH TO STR')
        if isinstance(_match, six.string_types):
            try:
                _match = pipe.CPWorkDir(_match)
                _LOGGER.debug(' - CONVERTED MATCH TO WORK DIR')
            except ValueError:
                _LOGGER.debug(' - FAILED TO CONVERT MATCH TO WORK DIR')

        # Obtain work dir
        if isinstance(_match, CPWorkDir):
            if pipe.MASTER == 'disk':
                _ety = self.obt_entity(_match.entity)
                assert isinstance(_ety, CCPEntity)
                _result = single([
                    _work_dir for _work_dir in _ety.work_dirs
                    if _work_dir == _match], catch=True)
            elif pipe.MASTER == 'shotgrid':
                _job = self.obt_job(_match.job)
                _result = _job.obt_work_dir(_match)
            else:
                raise NotImplementedError(pipe.MASTER)
            return _result

        _LOGGER.debug(' - FAILED TO CONVERT MATCH %s', _match)
        raise NotImplementedError(match)

    def obt_work(self, match):
        """Obtain the given work file object.

        Args:
            match (any): work to match

        Returns:
            (CCPWork): matching work file
        """
        _match = match
        _LOGGER.debug('OBJ WORK %s', _match)
        if isinstance(_match, six.string_types):
            _match = to_work(_match)
        if isinstance(_match, CPWork):
            _LOGGER.debug(' - WORK %s', _match)
            _work_dir = self.obt_work_dir(_match.work_dir)
            _LOGGER.debug(' - WORK DIR %s', _work_dir)
            if not _work_dir:
                return None
            _works = [_work for _work in _work_dir.works
                      if _work == _match]
            return single(_works, catch=True)

        raise NotImplementedError(match)

    @pipe_cache_result
    def obt_output(self, match, catch=False, force=False):
        """Obtain an output within this cache.

        Args:
            match (any): token to match with output
            catch (bool): no error if no output found
            force (bool): force outputs list to recache

        Returns:
            (CPOutput): output
        """
        from .. import cache

        _LOGGER.debug('FIND OUTPUT %s', match)
        _match = match
        if (
                not isinstance(_match, CPOutputBase) and
                isinstance(_match, Path)):
            _match = _match.path
            _LOGGER.debug(' - CONVERT TO STRING %s', match)

        # Convert a string to an output
        if isinstance(_match, six.string_types):
            _LOGGER.debug(' - CONVERT TO OUTPUT')
            try:
                _match = to_output(_match)
            except ValueError:
                _LOGGER.debug(' - FAILED TO CONVERT TO OUTPUT')
                if '/' in _match:
                    raise ValueError('Path is not output '+_match)
                if not _match:
                    raise ValueError('Empty path')
                raise NotImplementedError(match)

        if isinstance(_match, CPOutputBase):
            _LOGGER.debug(' - OBTAINED OUTPUT %s', _match)

            # Try as work dir output
            if _match.work_dir:
                _work_dir = self.obt_work_dir(_match.work_dir)
                _LOGGER.debug(' - WORK DIR %s', _work_dir)
                assert isinstance(_work_dir, CCPWorkDir)
                assert isinstance(_work_dir.entity, CCPEntity)
                _out = single(_out for _out in _work_dir.outputs
                              if _out == _match)
                assert isinstance(_out.entity, CCPEntity)

            # Must be entity level output
            else:
                _ety = self.obt_entity(_match.entity)
                _LOGGER.debug(' - ENTITY %s', _ety)
                assert isinstance(_ety, CCPEntity)
                try:
                    _out = _ety.obt_output(_match, catch=catch, force=force)
                except ValueError:
                    raise ValueError(
                        'Failed to find output {}'.format(_match.path))

            if _out:
                _LOGGER.debug(' - FOUND OUTPUT %s', _out)
                assert isinstance(_out, cache.CCPOutputBase)

            return _out

        raise NotImplementedError(match)

    def obt_output_seq_dir(self, dir_, force=False):
        """Obtain an output sequence directory from the cache.

        Args:
            dir_ (str): path to output sequence directory
            force (bool): force reread output sequence directories
                in the parent entity cache

        Returns:
            (CCPOutputSeqDir): output sequence directory
        """
        _ety_c = self.obt_entity(dir_)
        return _ety_c.obt_output_seq_dir(dir_, force=force)

    def reset(self):
        """Reset this cache and reread all contents."""
        _LOGGER.info('RESETTING CACHE age=%s',
                     nice_age(time.time() - self.ctime, depth=2))
        flush_caches(namespace='pipe')
        flush_caches(namespace='shotgrid')
        self.ctime = time.time()

    def __repr__(self):
        return '<{}>'.format(type(self).__name__)
