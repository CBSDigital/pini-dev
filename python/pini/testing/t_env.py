"""Tools for managing testing environment variables."""

import functools
import logging
import os
import sys

from pini.utils import abs_path, Path, passes_filter

_LOGGER = logging.getLogger(__name__)


def _add_sys_path(path, action):
    """Add path to sys.path list.

    Any existing instances of this path are removed.

    Args:
        path (str): path to add
        action (str): how to add the path (insert/append)
    """
    _path = abs_path(path)
    if not os.path.exists(_path):
        raise OSError('Missing path ' + _path)
    while _path in sys.path:
        sys.path.remove(_path)

    if action == 'insert':
        sys.path.insert(0, _path)
    elif action == 'append':
        sys.path.append(_path)
    else:
        raise ValueError(action)


def append_sys_path(path):
    """Append path at the end of sys.path list.

    Any existing instances of this path are removed.

    Args:
        path (str): path to add
    """
    _add_sys_path(path, action='append')


def enable_error_catch(enabled):
    """Set enabled state of error catcher.

    Args:
        enabled (bool): state to apply
    """
    from pini.tools import error
    error.toggle(enabled=enabled)


def enable_file_system(enabled=True):
    """Set file system enabled.

    Disabling will cause a DebuggingError on any file system call.

    Args:
        enabled (bool): state to apply (None will toggle)
    """
    _enabled = enabled
    if _enabled is None:
        _enabled = os.environ.get('PINI_DISABLE_FILE_SYSTEM')

    if _enabled:
        if 'PINI_DISABLE_FILE_SYSTEM' in os.environ:
            del os.environ['PINI_DISABLE_FILE_SYSTEM']
        _LOGGER.info('ENABLED FILE SYSTEM')
    else:
        os.environ['PINI_DISABLE_FILE_SYSTEM'] = '1'
        _LOGGER.info('DISABLED FILE SYSTEM')


def enable_find_seqs(enabled=True):
    """Set finding file sequences enabled.

    Disabling will cause a DebuggingError on any find seqs call.

    Args:
        enabled (bool): state to apply
    """
    if enabled:
        if 'PINI_DISABLE_FIND_SEQS' in os.environ:
            del os.environ['PINI_DISABLE_FIND_SEQS']
        _LOGGER.info('ENABLED FIND SEQS')
    else:
        os.environ['PINI_DISABLE_FIND_SEQS'] = '1'
        _LOGGER.info('DISABLED FIND SEQS')


def enable_nice_id_repr(enabled=None):
    """Enable nice id in path repr method.

    Args:
        enabled (bool): enabled state
    """
    _enabled = enabled
    if _enabled is None:
        _enabled = not os.environ.get('PINI_REPR_NICE_IDS')

    if not _enabled:
        if 'PINI_REPR_NICE_IDS' in os.environ:
            del os.environ['PINI_REPR_NICE_IDS']
        _LOGGER.info('DISABLED NICE ID REPR')
    else:
        os.environ['PINI_REPR_NICE_IDS'] = '1'
        _LOGGER.info('ENABLED NICE ID REPR')


def enable_sanity_check(enabled=None):
    """Enable/disable sanity check via $PINI_DISABLE_SANITY_CHECK.

    Args:
        enabled (bool): enabled state
    """
    _enabled = enabled
    if _enabled is None:
        _enabled = bool(os.environ.get('PINI_DISABLE_SANITY_CHECK'))

    if _enabled:
        if 'PINI_DISABLE_SANITY_CHECK' in os.environ:
            del os.environ['PINI_DISABLE_SANITY_CHECK']
        _LOGGER.info('ENABLED SANITY CHECK')
    else:
        os.environ['PINI_DISABLE_SANITY_CHECK'] = '1'
        _LOGGER.info('DISABLED SANITY CHECK')


def insert_env_path(path, env):
    """Insert a path into an environment variable.

    eg. add to $MAYA_SCRIPT_PATH

    The path is added with the appropriate separator for the current OS.

    Args:
        path (str): path to add
        env (str): environment variable to add to
    """
    _path = Path(abs_path(path))
    if not _path.exists():
        raise OSError('Missing path ' + _path.path)
    if env not in os.environ:
        os.environ[env] = _path.path
        return
    if _path.path in read_env_paths(env):
        return
    assert _path.path not in read_env_paths(env)
    os.environ[env] = ''.join([_path.path, os.pathsep, os.environ[env]])
    assert _path.path in read_env_paths(env)


def insert_sys_path(path):
    """Insert path at the top of sys.path list.

    Any existing instances of this path are removed.

    Args:
        path (str): path to add
    """
    _add_sys_path(path, action='insert')


def print_sys_paths(sort=False):
    """Print sys paths.

    Args:
        sort (bool): sort items
    """
    _paths = [abs_path(_path) for _path in sys.path]
    if sort:
        _paths.sort()
    for _idx, _path in enumerate(_paths):
        if _paths.count(_path) > 1 and _paths.index(_path) != _idx:
            continue
        print(f'{os.path.exists(_path):d} {_path}')


def read_env_paths(env, existing=None, filter_=None):
    """Read paths from the given environment variable.

    Args:
        env (str): name of environment variable to read
        existing (bool): filter by existing state of paths
        filter_ (str): apply path filter

    Returns:
        (str list): paths
    """
    _val = os.environ.get(env, '')
    _paths = set()
    for _path in _val.split(os.pathsep):
        _path = abs_path(_path)
        if existing is not None and os.path.exists(_path) != existing:
            continue
        if not passes_filter(_path, filter_):
            continue
        _paths.add(_path)
    return sorted(_paths)


def remove_env_path(env, path):
    """Remove path from environment variable.

    Args:
        env (str): name of environment variable to read
        path (str): path to remove
    """
    _path = abs_path(path)
    _paths = read_env_paths(env)
    if _path not in _paths:
        return
    _paths.remove(_path)
    os.environ[env] = os.pathsep.join(_paths)


def reset_enable_filesystem(func):
    """Decorator to renable filesystem after running function.

    Args:
        func (fn): function to decorate

    Returns:
        (fn): decorated fn
    """

    @functools.wraps(func)
    def _reset_enable_filesystem_fn(*args, **kwargs):
        try:
            _result = func(*args, **kwargs)
        finally:
            enable_file_system(True)
        return _result

    return _reset_enable_filesystem_fn
