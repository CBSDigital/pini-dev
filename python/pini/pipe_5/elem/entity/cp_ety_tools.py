"""General tools for managing entities."""

import logging
import re

from pini import dcc
from pini.utils import to_str, norm_path

from ...cp_utils import map_path

_LOGGER = logging.getLogger(__name__)


def cur_entity(job=None):
    """Get the current entity (if any).

    Args:
        job (CPJob): force parent job (to facilitate caching)

    Returns:
        (CPEntity): current entity
    """
    try:
        return to_entity(dcc.cur_file(), job=job)
    except ValueError:
        return None


def find_entity(name):
    """Find entity matching the given name.

    Args:
        name (str): entity name (eg. hvtest_satan_220613/test010)

    Returns:
        (CPEntity): matching entity
    """
    from pini import pipe
    _job, _label = re.split('[./]', name)
    _job = pipe.find_job(_job)
    return _job.find_entity(_label)


def recent_entities():
    """Obtain list of recentnly used entities.

    Returns:
        (CPEntity list): entities
    """
    from pini import pipe
    _etys = []
    for _work in pipe.recent_work():
        if _work.entity in _etys:
            continue
        _etys.append(_work.entity)
    return _etys


def to_entity(match, job=None, catch=False):
    """Map the given path to an entity.

    Args:
        match (str): item to match to entity
        job (CPJob): force parent job (to facilitate caching)
        catch (bool): no error if no entity found

    Returns:
        (CPAsset|CPShot): asset/shot object
    """
    from pini import pipe
    _LOGGER.debug('TO ENTITY %s', match)

    if isinstance(match, (pipe.CPAsset, pipe.CPShot)):
        return match

    # Treat as job/shot label
    if isinstance(match, str) and match.count('/') == 1:
        _job_s, _ety_s = match.split('/')
        _job = job or pipe.find_job(_job_s)
        return _job.find_entity(_ety_s)

    # Treat as entity name
    if isinstance(match, str) and not norm_path(match).count('/'):
        _job = job or pipe.cur_job()
        if _job:
            return _job.find_entity(match, catch=catch)

    # Treat as path
    _path = to_str(match)
    _path = map_path(_path)
    _LOGGER.debug(' - MAPPED %s', _path)

    # Try as asset
    try:
        return pipe.CPAsset(_path, job=job)
    except ValueError:
        pass

    # Try as shot
    try:
        return pipe.CPShot(_path, job=job)
    except ValueError:
        pass

    if catch:
        return None
    raise ValueError(match)
