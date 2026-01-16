"""Tools for managing the pipeline root base class."""

import logging
import operator
import os

from pini.utils import Dir, passes_filter, single, apply_filter

_LOGGER = logging.getLogger(__name__)


class CPRootBase(Dir):
    """Represents a pipeline root."""

    _JOBS_CACHE = {}

    def find_job(self, match=None, name=None, catch=False, **kwargs):
        """Find a matching job in the cache.

        Args:
            match (str): match by name/path/filter
            name (str): match by exact name
            catch (bool): no error if no job found

        Returns:
            (CPJob): job
        """
        _LOGGER.debug('FIND JOBS')
        _jobs = self.find_jobs(**kwargs)
        _LOGGER.debug(' - FOUND %d JOBS', len(_jobs))

        if len(_jobs) == 1:
            return single(_jobs)

        _name_matches = [_job for _job in _jobs if _job.name == name]
        if len(_name_matches):
            return single(_name_matches)

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

    def find_jobs(self, cfg_name=None, **kwargs):
        """Find jobs in the current pipeline.

        Args:
            cfg_name (str): filter by config name

        Returns:
            (CPJob list): matching jobs
        """
        _LOGGER.debug('FIND JOBS %s', kwargs)
        from pini import pipe
        _jobs = []
        for _job in self._read_jobs():
            _LOGGER.debug(' - TESTING JOB %s', _job)

            if not pipe.passes_filters(_job, filter_attr='name', **kwargs):
                _LOGGER.debug(' - FILTERS REJECTED %s %s', _job, kwargs)
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

    def obt_job(self, name):
        """Factory to obtain job object.

        Once the first instance of a job is created, this object is
        always returned.

        Args:
            name (str): name of job to obtain object for

        Returns:
            (CPJob): job object
        """
        _LOGGER.debug('OBT JOB %s', name)
        _job = self._JOBS_CACHE.get(name)
        if not _job:
            _job = self.find_job(name=name)
            self._JOBS_CACHE[name] = _job
        return _job
