"""General tools for managing jobs."""

import logging

from pini import dcc
from pini.utils import to_str

_LOGGER = logging.getLogger(__name__)


def cur_job(class_=None):
    """Build a job object for the current job.

    Args:
        class_ (class): override job class

    Returns:
        (CPJob): current job
    """
    from pini import pipe
    _class = class_ or pipe.CPJob
    try:
        return _class(dcc.cur_file())
    except ValueError:
        return None


def to_job(name, catch=False):
    """Build a job object with the given name.

    Args:
        name (str): job name
        catch (bool): no error if no matching job found

    Returns:
        (CPJob): job
    """
    from pini import pipe
    _LOGGER.debug('TO JOB %s', name)

    # Determine path
    _name = to_str(name)
    if '/' not in _name:
        _path = pipe.JOBS_ROOT.to_subdir(_name)
    else:
        _path = _name
    _LOGGER.debug(' - PATH %s', _path)

    # Build job
    try:
        _job = pipe.CPJob(_path)
    except ValueError as _exc:
        if not catch:
            raise _exc
        _job = None
    _LOGGER.debug(' - JOB %s', _job)

    return _job
