"""General tools relating to caching data."""

import logging
import sys

_LOGGER = logging.getLogger(__name__)


class _CacheProperty(object):
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
    from pini.utils import TMP_PATH, is_pascal, Path, abs_path, HOME_PATH

    assert is_pascal(tool)

    # Determine root dir
    if mode == 'tmp':
        _root = TMP_PATH
    elif mode == 'home':
        _root = HOME_PATH+'/tmp'
    else:
        raise ValueError(mode)

    # Build format
    _path = Path(path)
    _fmt = (
        '{root}/{namespace}/{tool}/{dir}/'
        '{base}{py_ver}{dcc}{platform}_{{func}}.{extn}'.format(
            root=_root, dir=_path.dir.replace(':', ''),
            base=_path.base, tool=tool, namespace=namespace,
            py_ver='_py{:d}'.format(sys.version_info.major) if py_ver else '',
            dcc='_{}'.format(dcc.NAME) if dcc_ else '',
            platform='_{}'.format(sys.platform) if platform else '',
            extn=extn))

    # Apply path limit check
    if check_path_limit and len(_fmt) > 250:
        _LOGGER.info(' - CACHE FMT %d %s', len(_fmt), _fmt)
        raise RuntimeError(
            'Cache format too long ({:d} chars)'.format(len(_fmt)))

    return abs_path(_fmt)
