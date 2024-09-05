"""Tools for managing the pipeline cache.

This is a version of the pipeline api that caches key components
so that they're only read once. This object can be used to speed
up pipeline traversal in tools and avoid reread data that's used
more than once.

These cacheable objects can be distinguished from the generic pipeline
objects as their types have CCP prefix, rather than just CP.
"""

# pylint: disable=too-many-public-methods

import logging
import time

import six

from pini.utils import (
    single, passes_filter, nice_age, norm_path, Path, flush_caches)

from ... import elem
from .. import job, ccp_utils

_LOGGER = logging.getLogger(__name__)


class CCPRootBase(elem.CPRoot):
    """Base object for the pipeline cache.

    Used to store top-level information, eg. list of jobs.

    Also used to access cacheable versions of current work/entity etc.
    """

    def __init__(self, path):
        """Constructor.

        Args:
            path (str): jobs root
        """
        super().__init__(path)
        self.ctime = time.time()

    @property
    def cur_entity(self):
        """Find the cur entity (if any).

        Returns:
            (CCPEntity): current entity
        """
        _ety = elem.cur_entity(job=self.cur_job)
        if not _ety:
            return None
        return self.obt_entity(_ety)

    @property
    def cur_job(self):
        """Object the current job object.

        Returns:
            (CCPJob): current job
        """
        _LOGGER.debug('CUR JOB')
        _job = elem.cur_job()
        if not _job:
            return None
        return self.obt_job(_job)

    @property
    def cur_asset(self):
        """Find the current asset (if any).

        Returns:
            (CCPAsset): current asset
        """
        _asset = elem.cur_asset()
        if not _asset:
            return None
        return self.obt_entity(_asset)

    @property
    def cur_shot(self):
        """Find the current shot (if any).

        Returns:
            (CCPShot): current shot
        """
        _shot = elem.cur_shot()
        if not _shot:
            return None
        return self.obt_entity(_shot)

    @property
    def cur_work_dir(self):
        """Obtain current work directory.

        Returns:
            (CCPWorkDir): work dir
        """
        _work_dir = elem.cur_work_dir(entity=self.cur_entity)
        if not _work_dir:
            return None
        return self.obt_work_dir(_work_dir)

    @property
    def cur_work(self):
        """Find the current work file (if any).

        Returns:
            (CCPWork): current work
        """
        _LOGGER.debug('CUR WORK %s', self.cur_work_dir)
        _work = elem.cur_work()
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

    @ccp_utils.pipe_cache_result
    def obt_job(self, match):
        """Obtain a cacheable version of the given job.

        Args:
            match (str): job name to match

        Returns:
            (CCPJob): matching job
        """
        _LOGGER.debug('FIND JOB %s', match)

        _match = match
        if isinstance(_match, elem.CPJob):
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
                _job = elem.CPJob(_match)
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

    @ccp_utils.pipe_cache_on_obj
    def _read_jobs(self, class_=None, force=False):
        """Find valid jobs on the current server.

        Args:
            class_ (class): override job class
            force (bool): force reread jobs from disk

        Returns:
            (CCPJob list): list of jobs
        """
        _LOGGER.debug('FIND JOBS %s', self)
        _class = class_ or job.CCPJob
        _jobs = super()._read_jobs()
        _LOGGER.debug(' - JOBS %d %s', len(_jobs), _jobs)
        _c_jobs = [
            _class(path=_job.path, cache=self) for _job in _jobs
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
        _path = self.to_subdir(name)
        return job.CCPJob(path=_path, cache=self)

    def obt(self, obj):
        """Obtain the cache representation of the given object.

        Args:
            obj (any): pipeline object to retrieve from cache

        Returns:
            (any): cache representation
        """
        if isinstance(obj, elem.CPJob):
            return self.obt_job(obj)
        if isinstance(obj, (elem.CPAsset, elem.CPShot)):
            return self.obt_entity(obj)
        if isinstance(obj, elem.CPWork):
            return self.obt_work(obj)
        if isinstance(obj, elem.CPOutputBase):
            return self.obt_output(obj)
        if isinstance(obj, elem.CPWorkDir):
            return self.obt_work_dir(obj)
        raise NotImplementedError(obj)

    def obt_sequence(self, match):
        """Find a sequence object.

        Args:
            match (CPSequence): sequence to match

        Returns:
            (CCPSequence): matching sequence from cache
        """
        if isinstance(match, elem.CPSequence):
            _job = self.obt_job(match.job)
            return _job.obt_sequence(match)
        raise ValueError(match)

    @ccp_utils.pipe_cache_result
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
                _ety = elem.to_entity(_match)
                _LOGGER.debug(' - ENTITY %s', _ety)
                assert _ety
                _job = self.obt_job(_ety.job.name)
                assert isinstance(_job, job.CCPJob)
                return _job.obt_entity(_ety)

        raise NotImplementedError(match)

    def obt_work_dir(self, match):
        """Find the given work dir object.

        Args:
            match (any): work dir to match

        Returns:
            (CCPWorkDir): matching work dir
        """
        _LOGGER.debug('FIND WORK DIR %s', match)
        _match = match

        # Locate work dir to match
        if (
                not isinstance(_match, elem.CPWorkDir) and
                isinstance(_match, Path)):
            _match = _match.path
            _LOGGER.debug(' - CONVERTED MATCH TO STR')
        if isinstance(_match, six.string_types):
            try:
                _match = elem.CPWorkDir(_match)
                _LOGGER.debug(' - CONVERTED MATCH TO WORK DIR')
            except ValueError:
                _LOGGER.debug(' - FAILED TO CONVERT MATCH TO WORK DIR')

        # Obtain work dir
        if isinstance(_match, elem.CPWorkDir):
            return self._obt_work_dir_cacheable(_match)

        _LOGGER.debug(' - FAILED TO CONVERT MATCH %s', _match)
        raise NotImplementedError(match)

    def _obt_work_dir_cacheable(self, work_dir):
        """Obtain cacheable work dir from work dir object.

        Args:
            work_dir (CPWorkDir): work dir to read

        Returns:
            (CCPWorkDir): cacheable work dir
        """
        raise NotImplementedError

    def obt_work(self, match):
        """Obtain the given work file object.

        Args:
            match (any): work to match

        Returns:
            (CCPWork): matching work file
        """
        from ... import cache

        _match = match
        _LOGGER.debug('OBJ WORK %s', _match)
        if isinstance(_match, six.string_types):
            _match = elem.to_work(_match)

        if isinstance(_match, elem.CPWork):
            _LOGGER.debug(' - WORK %s', _match)
            _work_dir = self.obt_work_dir(_match.work_dir)
            _LOGGER.debug(' - WORK DIR %s', _work_dir)
            if not _work_dir:
                return None
            assert isinstance(_work_dir, cache.CCPWorkDir)
            _works = [_work for _work in _work_dir.works
                      if _work == _match]
            return single(_works, catch=True)

        raise NotImplementedError(match)

    @ccp_utils.pipe_cache_result
    def obt_output(self, match, catch=False, force=False):
        """Obtain an output within this cache.

        Args:
            match (any): token to match with output
            catch (bool): no error if no output found
            force (bool): force outputs list to recache

        Returns:
            (CPOutput): output
        """
        from ... import cache

        _LOGGER.debug('FIND OUTPUT %s', match)
        _match = match
        if (
                not isinstance(_match, elem.CPOutputBase) and
                isinstance(_match, Path)):
            _match = _match.path
            _LOGGER.debug(' - CONVERT TO STRING %s', match)

        # Convert a string to an output
        if isinstance(_match, six.string_types):
            _LOGGER.debug(' - CONVERT TO OUTPUT')
            try:
                _match = elem.to_output(_match)
            except ValueError:
                _LOGGER.debug(' - FAILED TO CONVERT TO OUTPUT')
                if '/' in _match:
                    raise ValueError('Path is not output '+_match)
                if not _match:
                    raise ValueError('Empty path')
                raise NotImplementedError(match)

        if isinstance(_match, elem.CPOutputBase):
            _LOGGER.debug(' - OBTAINED OUTPUT %s', _match)

            # Try as work dir output
            if _match.work_dir:
                _work_dir = self.obt_work_dir(_match.work_dir)
                _LOGGER.debug(' - WORK DIR %s', _work_dir)
                assert isinstance(_work_dir, cache.CCPWorkDir)
                assert isinstance(_work_dir.entity, cache.CCPEntity)
                _out = single(_out for _out in _work_dir.outputs
                              if _out == _match)
                assert isinstance(_out.entity, cache.CCPEntity)

            # Must be entity level output
            else:
                _ety = self.obt_entity(_match.entity)
                _LOGGER.debug(' - ENTITY %s', _ety)
                assert isinstance(_ety, cache.CCPEntity)
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

    def obt_cur_work(self):
        """Obtain current work file.

        Provided to accomodate for an artist opening a new scene outside pini,
        leaving the cache out of date.

        Returns:
            (CPWork|None): current work file if any
        """
        if self.cur_work:
            return self.cur_work
        if elem.cur_work():
            self.reset()
            assert self.cur_work
            return self.cur_work
        return None

    def reset(self):
        """Reset this cache and reread all contents."""
        _LOGGER.info('RESETTING CACHE age=%s',
                     nice_age(time.time() - self.ctime, depth=2))
        flush_caches(namespace='pipe')
        flush_caches(namespace='shotgrid')
        self.ctime = time.time()

    def __repr__(self):
        return '<{}>'.format(type(self).__name__)