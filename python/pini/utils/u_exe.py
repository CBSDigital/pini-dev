"""Tools for managing and finding system executables."""

import logging
import os
import sys

from .cache import cache_result
from .path import Dir

_LOGGER = logging.getLogger(__name__)


@cache_result
def _find_programs_exes(force=False):
    """Find all relevant exes in program files dirs.

    For now this is hardcoded to a few relevant vendors for
    efficiency.

    Args:
        force (bool): force re-read data from disk

    Returns:
        (File list): all exes
    """

    _app_roots = [
        'C:/Program Files',
        'C:/Program Files (x86)',
    ]

    # Find application dirs
    _app_dirs = []
    for _app_root in _app_roots:
        _LOGGER.debug(' - CHECKING APP ROOT %s', _app_root)
        _app_root = Dir(_app_root)
        if not Dir(_app_root).exists():
            continue
        for _vendor in [
                'Autodesk',
                'Adobe',
                'DJV',
                'DJV2',
                'Diffinity',
                'Shotgun',
                'ShotGrid',
                'Thinkbox',
                'VideoLAN',
        ]:
            _vendor_dir = _app_root.to_subdir(_vendor)
            _LOGGER.debug('   - CHECKING VENDOR DIR %s', _vendor_dir)
            if not _vendor_dir.exists():
                continue
            _app_dirs += [_vendor_dir]
            _app_dirs += _vendor_dir.find(
                type_='d', depth=1, catch_access_error=True,
                catch_missing=True, class_=True)

    # Search application dirs for exes
    _exes = []
    for _app_dir in _app_dirs:
        _LOGGER.debug(' - CHECKING APP DIR %s', _app_dir)
        for _dir in [_app_dir, _app_dir.to_subdir('bin')]:
            _dir_exes = _dir.find(
                type_='f', extn='exe', depth=1, class_=True,
                catch_missing=True)
            if _dir_exes:
                _LOGGER.debug('   - FOUND %d EXES %s', len(_dir_exes), _dir.path)
            _exes += _dir_exes

    return _exes


@cache_result
def _find_programs_exe(name, force=False):
    """Find exe in program files dirs.

    Args:
        name (str): exe to match
        force (bool): force re-read data from disk

    Returns:
        (File|None): matching exe (if any)
    """
    _exes = [_exe for _exe in _find_programs_exes(force=force)
             if _exe.base == name]
    if _exes:
        return _exes[0]
    return None


@cache_result
def _find_path_exe(name, force=False):
    """Find an executable in $PATH.

    Args:
        name (str): name of executable to find
        force (bool): force re-read data from disk

    Returns:
        (File|None): executable if one is found - otherwise None
    """
    _LOGGER.debug('FIND PATH EXE %s', name)
    if sys.platform == 'win32':
        _sep = ';'
    else:
        _sep = ':'

    for _path in os.environ['PATH'].split(_sep):
        _dir = Dir(_path)
        if sys.platform == 'win32':
            _exe = _dir.to_file(name + '.exe')
        else:
            _exe = _dir.to_file(name)
        _LOGGER.debug(' - CHECKING FILE %s', _exe)
        if _exe.exists(catch=True):
            return _exe

    return None


@cache_result
def find_exe(name, catch=True, force=False):
    """Find an executable on this system.

    Args:
        name (str): name of executable to find
        catch (bool): no error if fail to find exe
        force (bool): force search for exe on disk

    Returns:
        (File|None): executable if one is found - otherwise None
    """
    _LOGGER.debug('FIND EXE %s', name)
    _exe = _find_path_exe(name, force=force) or _find_programs_exe(name, force=force)
    if _exe:
        _LOGGER.debug(' - FOUND EXE %s', _exe)
        return _exe
    _LOGGER.debug(' - FAILED TO FIND EXE %s', _exe)
    if catch:
        return None
    raise OSError('Failed to find exe ' + name)
