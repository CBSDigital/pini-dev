"""Tools for managing and finding system executables.

Nomenclature for app exes:
<root>/<vendor>/<app>/<base>.exe
<root>/<vendor>/<app>/bin/<base>.exe

NOTE: nuke is a special case

EXAMPLES:

C:/Program Files/Adobe/Adobe Substance 3D Designer/
    Adobe Substance 3D Designer.exe
C:/Program Files/Adobe/Adobe Substance 3D Painter/
    Adobe Substance 3D Painter.exe
C:/Program Files/Autodesk/Maya2023/bin/maya.exe
C:/Program Files/DJV2/bin/djv.exe
C:/Program Files/ShotGrid/RV-2022.3.0/bin/rv.exe
C:/Program Files/Shotgun/Python3/python.exe
C:/Program Files/Side Effects Software/Houdini 19.5.805/bin/houdini.exe
C:/Program Files/Side Effects Software/Houdini 19.5.805/bin/mplay.exe
C:/Program Files/BorisFX/SynthEyes 2025/SynthEyes64.exe
C:/Program Files/Thinkbox/Deadline10/bin/deadlinecommand.exe
C:/Program Files/VideoLAN/VLC/vlc.exe

C:/Program Files/Diffinity/Diffinity.exe
C:/Program Files/Nuke14.1v5/Nuke14.1.exe
"""

import logging
import os

from .cache import cache_result
from .path import Dir, is_abs, abs_path, File
from .u_filter import passes_filter
from .u_misc import single

_LOGGER = logging.getLogger(__name__)
_N_ENV_PATHS = None
_N_ENV_PATHS_READ = 0


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

    # Check for env override
    _key = f'PINI_{name.upper()}_EXE'
    _LOGGER.debug(' - ENV KEY %s', _key)
    if _key in os.environ:
        return File(os.environ[_key])

    # Priorities pini exes
    _exes = [_exe for _exe in _read_pini_exes() if _exe.base == name]
    if _exes:
        return _exes[-1]

    # Try checking $PATH sequentially to avoid disk reads
    _exe = _find_path_env_exe(name)
    if _exe:
        return _exe

    # Handle fail
    if not catch:
        raise ValueError(name)
    return None


def find_exes(name=None, filter_=None):
    """Find exes matching the given name.

    Args:
        name (str): name of exe (eg. python)
        filter_ (str): apply name filter

    Returns:
        (File list): matching exe files
    """

    # Add pini exes last so find_exe priorities these ones
    _all_exes = []
    _all_exes += _read_path_env_exes()
    _all_exes += _read_pini_exes()

    _exes = []
    for _exe in _all_exes:
        if name and _exe.base != name:
            continue
        if filter_ and not passes_filter(_exe.base, filter_):
            continue
        if _exe not in _exes:
            _exes.append(_exe)
    return _exes


@cache_result
def _read_pini_exes():
    """Read pini relevant exes.

    This aims to reduce the number of disk reads by only checking for
    exes which pini uses.

    Returns:
        (File list): exes
    """
    _LOGGER.debug('READ PINI EXES')
    _progs = Dir('C:/Program Files')
    _vendor_dirs = _progs.find(depth=1, type_='d', class_=True)
    _vendors = [_vendor_dir.filename for _vendor_dir in _vendor_dirs]
    _LOGGER.debug(' - VENDORS %d %s', len(_vendors), _vendors)

    _check_exes = _build_check_exes(vendors=_vendors)

    # See which exes exist
    _exes = []
    for _exe in _check_exes:
        _LOGGER.debug(' - CHECK EXE %s', _exe)
        _rel_path = _progs.rel_path(_exe)
        _LOGGER.debug('   - REL PATH %s', _rel_path)
        _vendor = _rel_path.split('/', 1)[0]
        _LOGGER.debug('   - VENDOR %s', _vendor)
        if _vendor not in _vendors:
            _LOGGER.debug('   - MISSING VENDOR')
            continue
        if not _exe.exists():
            _LOGGER.debug('   - MISSING EXE')
            continue
        _exes.append(_exe)
    # pprint.pprint(_exes, width=200)
    return sorted(_exes)


def _build_check_exes(vendors):
    """Build a list of exes to check for.

    Args:
        vendors (str list): vendors on disk

    Returns:
        (File list): exes to check for
    """
    _progs = Dir('C:/Program Files')
    _check_exes = []

    # App name matches exe
    for _vendor, _app in [
            ('Adobe', 'Adobe Substance 3D Designer'),
            ('Adobe', 'Adobe Substance 3D Painter'),
    ]:
        _check_exes.append(_progs.to_file(f'{_vendor}/{_app}/{_app}.exe'))

    # Multiple apps in folder, exe in bin dir
    for _vendor, _app_head, _exe_bases in [
            ('Autodesk', 'Maya', ['bin/maya']),
            ('ShotGrid', 'RV-', ['bin/rv']),
            ('Shotgun', 'Python', ['python']),
            ('Side Effects Software', 'Houdini ', ['bin/houdini', 'bin/mplay']),
            ('Thinkbox', 'Deadline', ['bin/deadlinecommand']),
            ('BorisFX', 'SynthEyes', ['SynthEyes64']),
    ]:
        _LOGGER.debug(' - FIND %s VERS', _app_head)
        if _vendor not in vendors:
            continue
        _vers_dir = _progs.to_subdir(_vendor)
        _LOGGER.debug('   - VERS DIR %s', _vers_dir)
        _ver_dirs = _vers_dir.find(
            head=_app_head, depth=1, type_='d', catch_missing=True, class_=True)
        _LOGGER.debug('   - FOUND %d VER DIRS %s', len(_ver_dirs), _ver_dirs)
        for _ver_dir in _ver_dirs:
            _LOGGER.debug('    - ADDING VER DIR %s', _ver_dir)
            for _exe_base in _exe_bases:
                _exe = _ver_dir.to_file(f'{_exe_base}.exe')
                _check_exes.append(_exe)
                _LOGGER.debug('    - ADDING EXE %s', _exe)

    # Nuke vers
    _nk_vers = [_vendor for _vendor in vendors if _vendor.startswith('Nuke')]
    for _nk_ver in _nk_vers:
        _maj, _min = _nk_ver.split('v')
        _check_exes.append(_progs.to_file(f'{_nk_ver}/{_maj}.exe'))

    # Specific paths
    for _exe in [
            'DJV2/bin/djv.exe',
            'VideoLAN/VLC/vlc.exe',
            'Diffinity/Diffinity.exe',
    ]:
        _check_exes.append(_progs.to_file(_exe))

    return _check_exes


@cache_result
def _read_env_paths():
    """Read paths in $PATH environmnent variable.

    Returns:
        (str list): paths
    """
    global _N_ENV_PATHS
    _paths = [
        abs_path(_path)
        for _path in os.environ['PATH'].split(os.pathsep)]
    _N_ENV_PATHS = len(_paths)
    return _paths


@cache_result
def _find_exes_in_env_path(path):
    """Find exes in the given path, caching results.

    Args:
        path (str): path to read

    Returns:
        (File list): exes
    """
    global _N_ENV_PATHS_READ
    assert isinstance(path, str)
    assert is_abs(path)
    assert abs_path(path) == path
    _N_ENV_PATHS_READ += 1
    _exes = Dir(path).find(
        depth=1, extn='exe', type_='f', catch_missing=True,
        class_=True, catch_access_error=True)
    return _exes


def _find_path_env_exe(name):
    """Find a named exe in $PATH.

    Args:
        name (str): name of exe to search for

    Returns:
        (File|None): exe (if any)
    """
    _paths = _read_env_paths()
    for _idx, _path in enumerate(_paths):
        _path = abs_path(_path)
        _exes = _find_exes_in_env_path(_path)
        _match = single(
            [_exe for _exe in _exes if _exe.base == name],
            catch=True)
        if _match:
            _LOGGER.debug(
                ' - READ %.01f%% OF $PATH %s',
                _N_ENV_PATHS_READ / _N_ENV_PATHS * 100,
                _match)
            return _match
    return None


@cache_result
def _read_path_env_exes():
    """Read all exes in $PATH.

    Warning: this is slow.

    Returns:
        (File list): exes
    """
    _LOGGER.warning('READ $PATH EXES (SLOW)')
    _exes = []
    for _path in _read_env_paths():
        _path = abs_path(_path)
        _exes += _find_exes_in_env_path(_path)
    return _exes


# @cache_result
# def _find_app_exes(force=False):
#     """Find all relevant exes in program files dirs.

#     For now this is hardcoded to a few relevant vendors for
#     efficiency.

#     Args:
#         force (bool): force re-read data from disk

#     Returns:
#         (File list): all exes
#     """

#     # _app_roots = [
#     #     'C:/Program Files',
#     #     'C:/Program Files (x86)',
#     # ]

#     # _vendor_dirs = _read_vendor_dirs()
#     # _app_dirs = []

#     # # Add named vendors
#     # for _vendor in [
#     #         'Autodesk',
#     #         'Adobe',
#     #         'DJV',
#     #         'DJV2',
#     #         'Diffinity',
#     #         'Side Effects Software',
#     #         'Shotgun',
#     #         'ShotGrid',
#     #         'Thinkbox',
#     #         'VideoLAN',
#     # ]:
#     #     _app_dir = u_misc.single(
#     #         [_dir for _dir in _vendor_dirs if _dir.base == _vendor],
#     #         catch=True)
#     #     if _app_dir:
#     #         _app_dirs.append(_app_dir)

#     # # Add


#     # # Find application dirs
#     # _app_dirs = []
#     # for _app_root in _read_vendor_dirs():
#     #     _LOGGER.debug(' - CHECKING APP ROOT %s', _app_root)
#     #     _app_root = Dir(_app_root)
#     #     if not Dir(_app_root).exists():
#     #         continue
#     #         _vendor_dir = _app_root.to_subdir(_vendor)
#     #         _LOGGER.debug('   - CHECKING VENDOR DIR %s', _vendor_dir)
#     #         if not _vendor_dir.exists():
#     #             continue
#     #         _app_dirs += [_vendor_dir]
#     #         _app_dirs += _vendor_dir.find(
#     #             type_='d', depth=1, catch_access_error=True,
#     #             catch_missing=True, class_=True)

#     # Search application dirs for exes
#     _exes = []
#     for _vendor_dir in _read_vendor_dirs():
#         if _vendor_dir.filename.startswith('Nuke'):
#             continue
#         for _app_dir in _vendor_dir.find(depth=1, type_='d', class_=True):
#             if not _app_dir.filename[0].isupper():
#                 continue
#             _LOGGER.debug(' - CHECKING APP DIR %s', _app_dir)
#             for _dir in [_app_dir, _app_dir.to_subdir('bin')]:
#                 _dir_exes = _dir.find(
#                     type_='f', extn='exe', depth=1, class_=True,
#                     catch_missing=True)
#                 if _dir_exes:
#                     _LOGGER.debug(
#                         '   - FOUND %d EXES %s', len(_dir_exes), _dir.path)
#                 _exes += _dir_exes

#     return _exes


# @cache_result
# def _find_programs_exe(name, force=False):
#     """Find exe in program files dirs.

#     Args:
#         name (str): exe to match
#         force (bool): force re-read data from disk

#     Returns:
#         (File|None): matching exe (if any)
#     """
#     _exes = [_exe for _exe in _find_app_exes(force=force)
#              if _exe.base == name]
#     if _exes:
#         return _exes[0]
#     return None


# @cache_result
# def _find_path_env_exe(name, force=False):
#     """Find an executable in $PATH.

#     Args:
#         name (str): name of executable to find
#         force (bool): force re-read data from disk

#     Returns:
#         (File|None): executable if one is found - otherwise None
#     """
#     _LOGGER.debug('FIND PATH EXE %s', name)
#     if sys.platform == 'win32':
#         _sep = ';'
#     else:
#         _sep = ':'

#     for _path in os.environ['PATH'].split(_sep):
#         _dir = Dir(_path)
#         if sys.platform == 'win32':
#             _exe = _dir.to_file(name + '.exe')
#         else:
#             _exe = _dir.to_file(name)
#         _LOGGER.debug(' - CHECKING FILE %s', _exe)
#         if _exe.exists(catch=True):
#             return _exe

#     return None


# @cache_result
# def find_exe(name, catch=True, force=False):
#     """Find an executable on this system.

#     Args:
#         name (str): name of executable to find
#         catch (bool): no error if fail to find exe
#         force (bool): force search for exe on disk

#     Returns:
#         (File|None): executable if one is found - otherwise None
#     """
#     _LOGGER.debug('FIND EXE %s', name)
#     _exe = (
#         _find_path_env_exe(name, force=force) or
#         _find_programs_exe(name, force=force))
#     if _exe:
#         _LOGGER.debug(' - FOUND EXE %s', _exe)
#         return _exe
#     _LOGGER.debug(' - FAILED TO FIND EXE %s', _exe)
#     if catch:
#         return None
#     raise OSError('Failed to find exe ' + name)


# def find_exes(name=None, filter_=None):
#     """Find exes matching the given name.

#     Args:
#         name (str): name of exe (eg. python)

#     Returns:
#         (File list): matching exe files
#     """
#     _exes = []
#     for _exe in _read_exes():
#         if name and _exe.base != name:
#             continue
#         if filter_ and not u_filter.passes_filter(_exe.base, filter_):
#             continue
#         _exes.append(_exe)
#     return _exes


# @cache_result
# def _read_exes():

#     _exes = []
#     _exes += _find_app_exes()
#     return _exes


# @cache_result
# def _read_vendor_dirs():

#     # Read all vendor dirs
#     _dirs = []
#     for _root in [
#             'C:/Program Files',
#             'C:/Program Files (x86)',
#     ]:
#         _dirs += Dir(_root).find(type_='d', depth=1, class_=True)

#     # Filter to pini-relevant dirs
#     _named = [
#         'Autodesk',
#         'Adobe',
#         'DJV',
#         'DJV2',
#         'Diffinity',
#         'Side Effects Software',
#         'Shotgun',
#         'ShotGrid',
#         'Thinkbox',
#         'VideoLAN',
#     ]
#     _dirs = [
#         _dir for _dir in _dirs
#         if _dir.base.startswith('Nuke') or
#         _dir.base in _named]

#     return _dirs


# @cache_result
# def _read_app_dirs():

#     asdasd
#     _vendor_dirs = _read_vendor_dirs()
#     _app_dirs = []

#     # Add named vendors
#     _named = [
#         'Autodesk',
#         'Adobe',
#         'DJV',
#         'DJV2',
#         'Diffinity',
#         'Side Effects Software',
#         'Shotgun',
#         'ShotGrid',
#         'Thinkbox',
#         'VideoLAN',
#     ]:
#         _app_dir = u_misc.single(
#             [_dir for _dir in _vendor_dirs if _dir.base == _vendor],
#             catch=True)
#         if _app_dir:
#             _app_dirs.append(_app_dir)

#     # Add nuke dirs
#     _

#     return _app_dirs
