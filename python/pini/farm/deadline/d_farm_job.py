"""Tools for managing jobs on the farm."""

import bz2
import logging

from pini.utils import (
    build_cache_fmt, system, basic_repr, find_exe, File, strftime,
    cache_result, abs_path)

_LOGGER = logging.getLogger(__name__)


class CDFarmJob:
    """Represents an existing job on deadline."""

    def __init__(
            self, uid, batch_name, ctime, rtime, name, status, user, comment,
            path=None):
        """Constructor.

        Args:
            uid (str): job uid
            batch_name (str): job batch name
            ctime (float): job creation time
            rtime (float): job read time
            name (str): job name
            status (str): job status at read time
            user (str): job user
            comment (str): job comment
            path (str): path to job output
        """
        self.uid = uid
        self.batch_name = batch_name
        self.ctime = ctime
        self.rtime = rtime
        self.name = name
        self.status = status
        self.user = user
        self.comment = comment
        self.path = path

        self.cache_fmt = build_cache_fmt(
            path=self.uid, namespace='Farm', tool='DeadlineCommand',
            mode='home', extn='pkl')

    def strftime(self, fmt=None):
        """Apply strftime to this job's ctime.

        Args:
            fmt (str): override strftime format

        Returns:
            (str): formatted time str
        """
        return strftime(fmt, self.ctime)

    @cache_result
    def to_log(self, force=False):
        """Read log for this job.

        Args:
            force (bool): force reread from disk

        Returns:
            (str): log text
        """
        _cmd = (
            "GetJobErrorReportFilenames" if self.status == 'Failed'
            else "GetJobLogReportFilenames")
        _cmds = [find_exe('deadlinecommand'), _cmd, self.uid]
        _results = system(_cmds, verbose=1).split()

        if not _results:
            _LOGGER.info(' - NO LOGS FOUND')
            return None
        _log = File(abs_path(_results[-1]))
        assert _log.exists()

        _text = ''
        with bz2.open(_log.path, "rt") as bz_file:
            for _line in bz_file:
                _text += _line
        return _text

    def __eq__(self, other):
        if isinstance(other, CDFarmJob):
            return self.uid == other.uid
        return self.uid == other

    def __hash__(self):
        return hash(self.uid)

    def __lt__(self, other):
        return self.uid < other.uid

    def __repr__(self):
        return basic_repr(self, self.name)
