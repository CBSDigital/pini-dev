"""General utilities for shotgrid integration."""

import logging

from pini import icons, pipe
from pini.pipe import cache
from pini.utils import single, get_method_to_file_cacher, get_result_cacher

_LOGGER = logging.getLogger(__name__)
ICON = icons.find("Spiral Notepad")


def get_sg_result_cacher(use_args=()):
    """Get result cacher for the shotgrid cache namespace.

    Args:
        use_args (list): args to use as cache key

    Returns:
        (fn): result cacher generation function
    """
    return get_result_cacher(use_args=use_args, namespace='shotgrid')


def sg_cache_result(func):
    """Decorate to cache a function result to the shotgrid cache namespace.

    Args:
        func (fn): function to cache

    Returns:
        (fn): decorated function
    """
    _cacher = get_sg_result_cacher()
    return _cacher(func)


def sg_cache_to_file(func):
    """Cache the result of the given method to file using the pipe namespace.

    Args:
        func (fn): method to cache

    Returns:
        (fn): decorated method
    """
    _cacher = get_method_to_file_cacher(
        mtime_outdates=False, min_mtime=cache.CACHE_START, namespace='shotgrid')
    return _cacher(func)


def output_to_work(output):
    """Obtain work file for the given output.

    Args:
        output (CPOutput): output to find work file for

    Returns:
        (CPWork): work file
    """
    _LOGGER.debug('OUTPUT TO WORK %s', output.path)

    # Try metadata
    if 'src' in output.metadata:
        _path = pipe.map_path(output.metadata['src'])
        _work = pipe.CPWork(_path)
        return pipe.CACHE.obt_work(_work, catch=True)
    _LOGGER.debug(' - NO SRC IN METADATA')

    # Try mapping
    _mapped_work = output.to_work()
    _LOGGER.debug(' - MAPPED WORK %s', _mapped_work)
    if _mapped_work and _mapped_work.exists():
        return _mapped_work
    _LOGGER.debug(' - MAPPED DOES NOT EXIST')

    # Try search
    _search_work = single(
        output.entity.find_works(
            task=output.task, ver_n=output.ver_n, tag=output.tag),
        catch=True)
    if _search_work:
        return _search_work

    return None
