"""General utilities for the pipeline cache."""

from pini.utils import get_result_cacher, get_method_to_file_cacher

CACHE_START = 1729706863


def pipe_cache_result(func):
    """Decorate to cache a function result to the pipe namespace.

    Args:
        func (fn): function to cache

    Returns:
        (fn): decorated function
    """
    _cacher = get_result_cacher(namespace='pipe')
    return _cacher(func)


def pipe_cache_on_obj(func):
    """Cache the result of the given method to the pipe namespace.

    Args:
        func (fn): method to cache

    Returns:
        (fn): decorated method
    """
    _cacher = get_result_cacher(
        use_args=('self', ), namespace='pipe')
    return _cacher(func)


def pipe_cache_to_file(func):
    """Cache the result of the given method to file using the pipe namespace.

    Args:
        func (fn): method to cache

    Returns:
        (fn): decorated method
    """
    _cacher = get_method_to_file_cacher(
        mtime_outdates=False, min_mtime=CACHE_START, namespace='pipe')
    return _cacher(func)
