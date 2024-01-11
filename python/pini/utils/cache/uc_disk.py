"""Tools for managing caching to file."""

import functools
import logging

import six

from .uc_memory import obtain_results_cache
from ..u_error import DebuggingError

_LOGGER = logging.getLogger(__name__)


def get_file_cacher(file_):
    """Build file cacher decorator.

    Args:
        file_ (str): path to cache data to

    Returns:
        (fn): file cache function
    """

    def _file_cacher(func):

        @functools.wraps(func)
        def _file_cache_func(*args, **kwargs):
            from pini.utils import File
            _file = File(file_)
            _force = kwargs.get('force')
            if _force or not _file.exists():
                _result = func(*args, **kwargs)
                _file.write_yml(_result, force=True)
            else:
                _result = _file.read_yml()
            return _result

        return _file_cache_func

    return _file_cacher


def get_method_to_file_cacher(
        mtime_outdates=True, min_mtime=None, max_age=None,
        namespace='default'):
    """Build a caching decorator which saves a result to disk.

    If the result is calculated or read from disk, it's then stored in memory
    and this it then used as the result for subsequence calls of the method.

    This requires the object to have a cache_fmt attribute, which is used to
    determine the cache file for this attribute.

        eg. H:/tmp/pini/MyToolUsingCaching/{func}.yml

    Args:
        mtime_outdates (bool): use the object mtime to outdate the cache
            ie. if the object has been modified more recently than the
            cache then this renders the cache invalid and forces the
            result to be recalculated
        min_mtime (float): if the cache file's mtime is before then then
            it's ignored
        max_age (float): apply maximum cache age in seconds - if the cache
            file is older then the data will be regenerated
        namespace (str): namespace to cache to

    Returns:
        (func): method caching decorator
    """

    def _method_to_file_cacher_dec(func):

        _LOGGER.debug(
            'BUILDING METHOD TO FILE CACHER %s mtime_outdates=%s',
            func.__name__, mtime_outdates)

        @functools.wraps(func)
        def _method_cache_func(self, *args, **kwargs):

            from pini.utils import File

            _LOGGER.debug('EXEC METHOD CACHE FUNC %s mtime_outdates=%s',
                          func.__name__, mtime_outdates)
            _LOGGER.debug(' - CACHE FMT %s', self.cache_fmt)
            assert isinstance(self.cache_fmt, six.string_types)
            _key = func, self
            _LOGGER.debug(' - KEY %s', _key)
            _file = File(self.cache_fmt.format(func=func.__name__))
            _force = kwargs.get('force')
            _LOGGER.debug(' - CACHE FILE %s', _file.path)
            _results = obtain_results_cache(namespace)

            # Determine whether to recache
            _action = _determine_cache_action(
                force=_force, results=_results, key=_key, obj=self,
                file_=_file, mtime_outdates=mtime_outdates,
                min_mtime=min_mtime, max_age=max_age)
            _LOGGER.debug(' - CACHE ACTION %s', _action)

            # Obtain result
            if _action == 'recache':
                _result = func(self, *args, **kwargs)
                _LOGGER.debug(' - CALCULATED RESULT')
                _write_func = {
                    'yml': _file.write_yml,
                    'pkl': _file.write_pkl}[_file.extn]
                try:
                    _write_func(_result, force=True)
                except OSError:
                    _LOGGER.warning('FAILED TO WRITE CACHE %s', _file.path)
                _LOGGER.debug(' - WROTE CACHE')
                _results[_key] = _result
            elif _action == 'use memory':
                _result = _results[_key]
                _LOGGER.debug(' - USING MEMORY CACHE')
            elif _action == 'use disk':
                _LOGGER.debug(' - READING DISK CACHE')
                _read_func = {
                    'yml': _file.read_yml,
                    'pkl': _file.read_pkl}[_file.extn]
                try:
                    _result = _read_func()
                except DebuggingError as _exc:
                    raise _exc
                except RuntimeError:
                    _LOGGER.info(
                        ' - READING DISK CACHE FAILED %s', _file.path)
                    _result = func(self, *args, **kwargs)
                    _file.write_yml(_result, force=True)
                _results[_key] = _result
            else:
                raise ValueError(_action)

            return _result

        _LOGGER.debug(' - DECORATOR %s', _method_cache_func)

        return _method_cache_func

    return _method_to_file_cacher_dec


def _determine_cache_action(
        force, results, key, file_, obj, mtime_outdates, min_mtime,
        max_age):
    """Determine action to take on results request.

    Args:
        force (bool): force flag
        results (dict): cache results dict
        key (tuple): results key
        file_ (File): cache file
        obj (object): method's parent object
        mtime_outdates (bool): whether mtime outdates cache
        min_mtime (bool): min cache mtime to outdate cache
        max_age (float): apply maximum cache age (in seconds)

    Returns:
        (str): cache action
    """
    from pini.utils import File

    if force:
        _action = 'recache'
    elif max_age and file_.exists() and file_.age() > max_age:
        _action = 'recache'
    elif key in results:
        _action = 'use memory'
    elif not file_.exists():
        _action = 'recache'
    elif (  # Apply mtime outdates to files
            isinstance(obj, File) and
            mtime_outdates and
            file_.mtime() < obj.mtime()):
        _action = 'recache'
    elif min_mtime and file_.mtime() < min_mtime:
        _action = 'recache'
    else:
        _action = 'use disk'

    return _action


def cache_method_to_file(func):
    """Cache result of the given method to file.

    The method must belong to a File object and the File
    must have a cache_fmt property which is used to determine
    the path to cache to.

    eg. AAA.cache_fmt is set to /tmp/cache_{func}.yml
        if AAA.read_data is decorated, the result of a call
        to AAA.read_data will be saved to /tmp/cache_read_data.yml

    If the cache is older than the file itself then the data
    is reread.

    Args:
        func (fn): method to cache results of

    Returns:
        (fn): result cache version of method
    """
    _cacher = get_method_to_file_cacher()
    return _cacher(func)
