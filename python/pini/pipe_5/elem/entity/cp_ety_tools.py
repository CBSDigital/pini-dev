"""General tools for managing entities."""

import logging
import re

from pini import dcc
from pini.utils import to_str

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


def to_entity(path, job=None, catch=False):
    """Map the given path to an entity.

    Args:
        path (str): path to map
        job (CPJob): force parent job (to facilitate caching)
        catch (bool): no error if no entity found

    Returns:
        (CPAsset|CPShot): asset/shot object
    """
    from pini import pipe
    _LOGGER.debug('TO ENTITY %s', path)

    if isinstance(path, (pipe.CPAsset, pipe.CPShot)):
        return path

    # Treat as job/shot label
    if isinstance(path, str) and path.count('/') == 1:
        _job_s, _ety_s = path.split('/')
        _job = job or pipe.find_job(_job_s)
        return _job.find_entity(_ety_s)

    _path = to_str(path)
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
    raise ValueError(path)
