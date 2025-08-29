"""Tools for normalising and absoluting paths."""

import logging
import os

from ..u_misc import check_logging_level

from . import up_utils

_LOGGER = logging.getLogger(__name__)


def abs_path(path, win=False, root=None, mode=None):
    r"""Make the given path absolute and normalised.

    eg. C://path -> C:/path
        c://path -> C:/path
        c:\path -> C:/path

    Args:
        path (str): path to process
        win (bool): use windows normalisation (eg. C:\path)
            [DEPRECATED - use mode='win']
        root (str): override cwd as root
        mode (str): pathing mode
            drive - replace UNC paths for disk mounts
                eg: //mount/Projects -> P:
                NOTE: mapping must be set up using $PINI_ABS_PATH_DRIVE_MAP
            win - use windows normalisation (eg. C:\path)

    Returns:
        (str): absolute path
    """
    from .up_path import Path

    check_logging_level()

    # Get/check path string
    _path = path
    if isinstance(_path, Path):
        _path = _path.path
    if not isinstance(_path, str):
        raise ValueError(f'bad type {_path} ({type(_path).__name__})')
    _path = str(_path)  # convert unicode
    _path = _path.strip('"')
    _LOGGER.debug('ABS PATH %s', _path)

    _path = _apply_prefix_fixes(_path)
    _path = norm_path(_path)

    # Apply allowed root
    _env = os.environ.get('PINI_ABS_PATH_ALLOW_ROOTS', '')
    _allowed_roots = [_item for _item in _env.split(';') if _item]
    _LOGGER.debug(' - ALLOWED ROOTS %s', _allowed_roots)
    for _root in _allowed_roots:
        if not _path.startswith(_root):
            continue
        _LOGGER.debug(' - APPLY ALLOWED ROOT %s', _root)
        return _root + norm_path(_path[len(_root):])

    _path = _apply_replace_root(_path, env='PINI_ABS_PATH_REPLACE_ROOTS')
    _path = _fix_non_abs_path(_path, root=root)

    # Fix windows drive without leading slash eg. V:pipeline
    if len(_path) >= 3 and _path[1] == ':' and _path[2] != '/':
        _path = _path[:2] + '/' + _path[2:]

    _path = norm_path(_path)
    _path = _apply_mode(_path, mode=mode, win=win)

    return _path


def _apply_mode(path, mode, win):
    r"""Apply pathing mode.

    Args:
        path (str): path to process
        mode (str): pathing mode
        win (bool): use windows normalisation (eg. C:\path)

    Returns:
        (str): path with mode applied
    """
    _path = path

    _mode = mode
    if win:
        from pini.tools import release
        release.apply_deprecation('04/08/25', 'Use mode="win"')
        assert not _mode
        _mode = 'win'

    if _mode is None:
        pass
    elif _mode == 'win':
        _path = _path.replace('/', '\\')
    elif _mode == 'drive':
        _path = _apply_replace_root(_path, env='PINI_ABS_PATH_DRIVE_MAP')
    else:
        raise ValueError(_mode)

    return _path


def _apply_prefix_fixes(path):
    """Apply basic prefix fixes.

    Args:
        path (str): path to process

    Returns:
        (str): path with prefixes updated
    """
    _path = path
    if _path == '~':
        _path = up_utils.HOME_PATH
    elif _path.startswith('~/'):
        _path = up_utils.HOME_PATH + _path[1:]
    elif _path.startswith('file:///'):
        _path = _path.replace('file:///', '', 1)
        if len(_path) > 2 and _path[1] != ':':  # Fix linux style
            _path = '/' + _path
    return _path


def _fix_non_abs_path(path, root):
    """Fix non-absolute path.

    Args:
        path (str): path to process
        root (str): override cwd as root

    Returns:
        (str): absolute path
    """
    _path = path
    _LOGGER.debug(' - IS ABS %d %s', is_abs(_path), _path)
    if not is_abs(_path):
        _root = norm_path(root or os.getcwd())
        _path = _root + '/' + _path
        _LOGGER.debug(' - UPDATED %s', _path)
    return _path


def _apply_replace_root(path, env):
    """Apply env mapping root replacement.

    This can be used to apply an OS change or to unify alternative mounts.
    Any paths within the left hand root will be updated to use the right
    hand root.

    Args:
        path (str): path to update
        env (str): mapping environment variable to read
            eg. PINI_ABS_PATH_REPLACE_ROOTS

    Returns:
        (str): updated path
    """
    _path = path
    _replace_roots = _read_map_var(env)
    _LOGGER.debug(' - REPLACE ROOTS %s', _replace_roots)
    for _find, _replace in _replace_roots:
        if _path.startswith(_find):
            _LOGGER.debug(' - REPLACE ROOT %s -> %s', _find, _replace)
            _path = _replace + _path[len(_find):]
            _LOGGER.debug(' - UPDATE %s', _path)
    return _path


def _read_map_var(env):
    """Read a mapping environment variable.

    eg. '//mount/tools>>T:;//mount/projects>>P:'
       -> [('//mount/tools', 'T:'), '//mount/projects', 'P:')]

    Args:
        env (str): environment variable to read (eg.

    Returns:
        (tuple list): mappings
    """
    _map_s = os.environ.get(env, '')
    return [_item.split('>>>') for _item in _map_s.split(';') if _item]


def is_abs(path):
    """Test if the given path is absolute.

    Args:
        path (str): path to test

    Returns:
        (bool): whether path is absolute
    """
    if not path:
        return False
    return path.startswith('/') or (len(path) >= 2 and path[1] == ':')


def norm_path(path):
    """Normalise the given path.

    Args:
        path (str): path to normalise

    Returns:
        (str): normalised path
    """
    _path = path
    if _path is None:
        raise ValueError(_path)

    # Handle Path/Seq objects
    if hasattr(_path, 'path') and isinstance(_path.path, str):
        _path = _path.path

    _path = _path.strip('"')
    try:
        _path = os.path.normpath(_path).replace('\\', '/')
    except AttributeError as _exc:
        raise ValueError(_path) from _exc

    # Normalise drive letter
    if is_abs(_path):
        if len(_path) >= 3 and _path[0] == _path[2] == '/':  # eg. /c/blah
            _path = _path[1].upper() + ":" + _path[2:]
        elif len(_path) >= 2 and _path[1] == ':':
            _path = _path[0].upper() + _path[1:]
        elif _path.startswith('/'):  # Linux style
            pass
        else:
            raise ValueError(_path)

    # Update home tilda
    if _path.startswith('~'):
        assert _path.count('~') == 1
        _path = _path.replace('~', up_utils.HOME_PATH)

    return str(_path)
