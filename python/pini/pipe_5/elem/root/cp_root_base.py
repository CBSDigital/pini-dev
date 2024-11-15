"""Tools for managing the pipeline root base class."""

import logging
import operator
import os

from pini.utils import Dir, passes_filter, single, apply_filter

_LOGGER = logging.getLogger(__name__)


class CPRootBase(Dir):
    """Represents a pipeline root."""

    _JOBS_CACHE = {}

    def find_job(self, match=None, filter_=None, name=None, catch=False):
        """Find a matching job in the cache.

        Args:
            match (str): match by name/path
            filter_ (str): job name filter
            name (str): match by name
            catch (bool): no error if no job found

        Returns:
            (CPJob): job
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

    # def find_job(self, match=None, filter_=None, catch=False):
    #     """Find a job.

    #     Args:
    #         match (str): name to match
    #         filter_ (str): apply filter to jobs list
    #         catch (bool): no error of exactly one job isn't found

    #     Returns:
    #         (CPJob): matching job (if any)
    #     """
    #     _LOGGER.debug('FIND JOB %s', match)
    #     _jobs = self.find_jobs(filter_=filter_)

    #     # Try single job
    #     _job = single(_jobs, catch=True)
    #     if _job:
    #         return _job

    #     # Try name match
    #     _match_job = single(
    #         [_job for _job in _jobs if _job.name == match], catch=True)
    #     if _match_job:
    #         return _match_job

    #     # Try filter match
    #     _filter_jobs = apply_filter(
    #         _jobs, match, key=operator.attrgetter('name'))
    #     _LOGGER.debug(' - FILTER JOBS %d %s', len(_filter_jobs), _filter_jobs)
    #     if len(_filter_jobs) == 1:
    #         return single(_filter_jobs)

    #     if catch:
    #         return None
    #     raise ValueError(match)

    def find_jobs(self, filter_=None, cfg_name=None):
        """Find jobs in the current pipeline.

        Args:
            filter_ (str): apply filter to jobs list
            cfg_name (str): filter by config name

        Returns:
            (CPJob list): matching jobs
        """
        _jobs = []
        for _job in self._read_jobs():
            _LOGGER.debug(' - TESTING JOB %s', _job)
            if not passes_filter(_job.name, filter_):
                continue
            if cfg_name and (
                    not _job.cfg_file.exists(catch=True) or
                    _job.cfg['name'] != cfg_name):
                continue
            _jobs.append(_job)
        return _jobs

    def _read_jobs(self, class_=None):
        """Read all jobs in the current pipeline.

        Args:
            class_ (class): override job class

        Returns:
            (CPJob list): matching jobs
        """
        from pini import pipe

        _class = class_ or pipe.CPJob
        _filter = os.environ.get('PINI_PIPE_JOBS_FILTER')
        _LOGGER.debug('READ JOBS %s %s', _class, self.path)

        _jobs = []
        for _dir in self._read_job_dirs():
            _LOGGER.debug(' - TESTING DIR %s', _dir)
            _job = _class(_dir)
            if _filter and not passes_filter(_job.name, _filter):
                continue
            if _job.name not in self._JOBS_CACHE:
                self._JOBS_CACHE[_job.name] = _job
            _jobs.append(_job)

        return _jobs

    def _read_job_dirs(self):
        """Read paths to jobs.

        Returns:
            (str list): job dir paths
        """
        raise NotImplementedError

    def obt_job(self, match):
        """Factory to obtain job object.

        Once the first instance of a job is created, this object is
        always returned.

        Args:
            match (str): name of job to obtain object for

        Returns:
            (CPJob): job object
        """
        _LOGGER.debug('OBT JOB %s', match)
        _job = self._JOBS_CACHE.get(match)
        if not _job:
            _job = self.find_job(match)
            self._JOBS_CACHE[match] = _job
        return _job
