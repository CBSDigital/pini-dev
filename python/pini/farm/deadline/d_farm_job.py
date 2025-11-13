"""Tools for managing jobs on the farm."""

import logging
import time

from pini.utils import (
    build_cache_fmt, system, basic_repr, cache_method_to_file, find_exe,
    File, strftime)

_LOGGER = logging.getLogger(__name__)


class CDFarmJob:
    """Represents an existing job on deadline."""

    def __init__(self, uid):
        """Constructor.

        Args:
            uid (str): job uid
        """
        self.uid = uid
        self.cache_fmt = build_cache_fmt(
            path=self.uid, namespace='Farm', tool='DeadlineCommand',
            mode='home', extn='pkl')

    @property
    def batch_name(self):
        """Obtain batch name for this job.

        Returns:
            (str): batch name
        """
        return self.to_details()['Batch Name']

    @property
    def ctime(self):
        """Obtain creation time of this job (from start time).

        Returns:
            (float): creation time
        """
        _ctime_s = self.to_details()['Start Date']
        return time.strptime(_ctime_s, '%Y/%m/%d %H:%M:%S')

    @property
    def name(self):
        """Obtain job name for this job.

        Returns:
            (str): name
        """
        return self.to_details()['Name']

    def strftime(self, fmt=None):
        """Apply strftime to this job's ctime.

        Args:
            fmt (str): override strftime format

        Returns:
            (str): formatted time str
        """
        return strftime(fmt, self.mtime)

    def to_details(self):
        """Obtain details for this job.

        Returns:
            (dict): job details
        """
        _lines = self._read_details_str().split('\n')
        _data = {}
        for _line in _lines:
            _line = _line.strip()
            if ':' not in _line:
                continue
            _key, _val = _line.split(':', 1)
            _data[_key] = _val
        return _data

    def _check_for_details(self):
        """Check whether details have been read.

        Returns:
            (bool): whether details metadata cache exists
        """
        _func = self._read_details_str.__name__
        _file = File(self.cache_fmt.format(func=_func))
        return _file.exists()

    @cache_method_to_file
    def _read_details_str(self):
        """Read details for this job.

        Returns:
            (str): detail string
        """
        _cmds = [
            find_exe('deadlinecommand'), '-GetJobDetails', self.uid]
        _LOGGER.info(' - READ JOB METADATA %s', self.uid)
        _LOGGER.info(' - CACHE FMT %s', self.cache_fmt)
        return system(_cmds, verbose=1)

    def __repr__(self):
        if self._check_for_details():
            _name = self.name
        else:
            _name = self.uid
        return basic_repr(self, _name)
