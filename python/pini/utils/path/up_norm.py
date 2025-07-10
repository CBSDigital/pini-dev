"""Tools for normalising and absoluting paths."""

import logging
import os

from ..u_misc import check_logging_level

from . import up_utils

_LOGGER = logging.getLogger(__name__)


def abs_path(path, win=False, root=None):
    r"""Make the given path absolute and normalised.

    eg. C://path -> C:/path
        c://path -> C:/path
        c:\path -> C:/path

    Args:
        path (str): path to process
        win (bool): use windows normalisation (eg. C:\path)
        root (str): override cwd as root

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
    if _path == '~':
        _path = up_utils.HOME_PATH
    elif _path.startswith('~/'):
        _path = up_utils.HOME_PATH + _path[1:]
    elif _path.startswith('file:///'):
        _path = _path.replace('file:///', '', 1)
        if len(_path) > 2 and _path[1] != ':':  # Fix linux style
            _path = '/' + _path
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

    _path = _apply_replace_root(_path)

    # Fix non-abs paths
    _LOGGER.debug(' - IS ABS %d %s', is_abs(_path), _path)
    if not is_abs(_path):
        _root = norm_path(root or os.getcwd())
        _path = _root + '/' + _path
        _LOGGER.debug(' - UPDATED %s', _path)

    # Fix windows drive without leading slash eg. V:pipeline
    if len(_path) >= 3 and _path[1] == ':' and _path[2] != '/':
        _path = _path[:2] + '/' + _path[2:]

    # Normalise
    _path = norm_path(_path)
    _LOGGER.debug(' - NORMALISED %s', _path)
    if win:
        _path = _path.replace('/', '\\')

    return _path


def _apply_replace_root(path):
    """Apply $PINI_ABS_PATH_REPLACE_ROOTS root replacement.

    This can be used to apply an OS change or to unify alternative mounts.

    eg. os.environ['PINI_ABS_PATH_REPLACE_ROOTS'] = ';'.join([
        'S:/Projects>>>/mnt/projects',
        'T:/Pipeline>>>/mnt/pipeline'])

    Any paths within the left hand root will be updated to use the right
    hand root.

    Args:
        path (str): path to update

    Returns:
        (str): updated path
    """
    _path = path
    _env = os.environ.get('PINI_ABS_PATH_REPLACE_ROOTS')
    if not _env:
        return _path

    _replace_roots = [_item.split('>>>') for _item in _env.split(';') if _item]
    _LOGGER.debug(' - REPLACE ROOTS %s', _replace_roots)
    for _find, _replace in _replace_roots:
        if _path.startswith(_find):
            _LOGGER.debug(' - REPLACE ROOT %s -> %s', _find, _replace)
            _path = _replace + _path[len(_find):]
            _LOGGER.debug(' - UPDATE %s', _path)

    return _path


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
