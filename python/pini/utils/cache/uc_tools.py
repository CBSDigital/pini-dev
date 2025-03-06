"""General tools relating to caching data."""

import logging
import sys

_LOGGER = logging.getLogger(__name__)


class CacheOutdatedError(RuntimeError):
    """Used to signify a cache being out of date."""


class _CacheProperty:
    """Acts like a property but the result is stored."""

    def __init__(self, func):
        """Constructor.

        Args:
            func (fn): property style method to decorate
        """
        self.func = func

    def __get__(self, obj, type_):
        if obj is None:
            return self.func
        _value = self.func(obj)
        setattr(obj, self.func.__name__, _value)
        return _value


def cache_property(func):
    """Property decorator which stores the result.

    NOTE: this cannot be recached - if recaching is required then the data
    should be cached in a function and then that result should be accessed
    via a regular property.

    Args:
        func (fn): property style method to decorate

    Returns:
        (CacheProperty): cache property decorator
    """
    return _CacheProperty(func)


def build_cache_fmt(
        path, tool, mode='tmp', namespace='pini', py_ver=False, dcc_=False,
        platform=False, check_path_limit=True, extn='yml'):
    """Build cache format string.

    This is used by the method to file cacher to build a path for
    a cache yml file. Generally this will be caching data relating
    to a file, so the file path is included in the cache format to
    give each file a unique set of cache files.

    eg. cache format for this path:
        C:/Test/file.txt

        might be something like:
        $TMP/pini/myTool/C/Test/file_{func}.yml

    Args:
        path (str): path which cache relates to
        tool (str): name of tool using cache (eg. PiniHelper)
        mode (str): cache mode (eg. tmp/home)
        namespace (str): namespace of cache (suite of tools using cache)
        py_ver (bool): include python version in cache path
        dcc_ (bool): include dcc in cache path
        platform (bool): include platform in cache path
        check_path_limit (bool): check windows path limit
        extn (str): cache extension
            yml - slower but readable
            pkl - around 100x faster

    Returns:
        (str): cache format
    """
    from pini import dcc
    from pini.utils import TMP, is_pascal, Path, abs_path, HOME, to_str

    assert is_pascal(tool)

    # Determine root dir
    if mode == 'tmp':
        _root = TMP.to_subdir('.pini/cache')
    elif mode == 'home':
        _root = HOME.to_subdir('.pini/cache')
    else:
        raise ValueError(mode)

    _path = to_str(path)
    _path = _path.replace('{', '_')
    _path = _path.replace('}', '_')
    _path = Path(_path)

    # Build format
    _dir_s = _path.dir.replace(':', '')
    _py_ver_s = f'_py{sys.version_info.major:d}' if py_ver else ''
    _dcc_s = f'_{dcc.NAME}' if dcc_ else ''
    _platform_s = f'_{sys.platform}' if platform else ''
    _fmt = (
        f'{_root}/{namespace}/{tool}/{_dir_s}/'
        f'{_path.base}{_py_ver_s}{_dcc_s}{_platform_s}_{{func}}.{extn}')

    # Apply path limit check
    if check_path_limit and len(_fmt) > 250:
        _LOGGER.info(' - CACHE FMT %d %s', len(_fmt), _fmt)
        raise RuntimeError(
            f'Cache format too long ({len(_fmt):d} chars)')

    return abs_path(_fmt)
