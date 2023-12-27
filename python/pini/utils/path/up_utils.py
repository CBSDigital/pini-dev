"""General utilities for managing paths."""

# pylint: disable=anomalous-backslash-in-string

import functools
import getpass
import logging
import os
import tempfile

import six

from ..u_error import DebuggingError
from ..u_misc import dprint, lprint

_LOGGER = logging.getLogger(__name__)


def _read_mounts():
    """Get a list of mounted drives.

    Returns:
        (str list): mounted drive root paths
    """
    _letters = [chr(_idx) for _idx in range(ord('A'), ord('Z')+1)]
    _mounts = []
    for _letter in _letters:
        _path = _letter + ":/"
        if os.path.exists(_path):
            _mounts.append(_path)
    return _mounts


_MOUNTS = _read_mounts()


def _get_home_dir():
    """Get path to home dir (not including Documents dir).

    Returns:
        (str): home dir path
    """
    if 'PINI_HOME' in os.environ:
        _home = os.environ['PINI_HOME']
    elif 'HOME' in os.environ:
        _home = os.environ['HOME']
    else:
        _home = os.path.expanduser("~")
    _home = _home.replace('\\', '/')
    _LOGGER.debug('GET HOME DIR %s', _home)

    # Check for clean mount
    _user = getpass.getuser()
    if _home.count(_user) == 1:
        _home_root, _ = _home.split(_user)
        _home_tail = _home[len(_home_root):].lstrip('/')
        _LOGGER.debug(' - CHECKING MOUNTS %s %s', _home_tail, _MOUNTS)
        for _mount in _MOUNTS:
            _mount_home = os.path.abspath(_mount + '/' + _home_tail)
            if os.path.exists(_mount_home):
                _home = _mount_home.replace('\\', '/')
                _LOGGER.debug(' - UPDATED TO MOUNT %s', _home)
                break

    return _home


HOME_PATH = _get_home_dir()


def _get_tmp_dir():
    """Get path to temp dir.

    Returns:
        (str): path to temp
    """
    _LOGGER.debug('GET TMP DIR')
    _tmp = tempfile.gettempdir()
    _LOGGER.debug(' - TMP DIR %s (A)', _tmp)
    _tmp = os.path.normpath(_tmp).replace('\\', '/')
    _LOGGER.debug(' - TMP DIR %s (B)', _tmp)

    # Fix lowercase drive name
    if len(_tmp) >= 2 and _tmp[1] == ':' and _tmp[0].islower():
        _tmp = _tmp[0].upper() + _tmp[1:]

    # Update cropped home (eg. c:/users/hvande~1)
    _user = getpass.getuser()
    _LOGGER.debug(' - USER %s', _user)
    for _cropped_user in [
            _user[:6]+'~1',
            _user[:6].upper()+'~1',
    ]:
        _LOGGER.debug(' - CROPPED USER %s', _cropped_user)
        if _tmp.count(_cropped_user) == 1:
            _tmp = _tmp.replace(_cropped_user, _user)

    _LOGGER.debug(' - TMP DIR %s (Z)', _tmp)
    return _tmp


TMP_PATH = _get_tmp_dir()


def abs_path(path, win=False, root=None):
    """Make the given path absolute and normalised.

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

    # Get/check path string
    _path = path
    if isinstance(_path, Path):
        _path = _path.path
    if not isinstance(_path, six.string_types):
        raise ValueError('bad type {}'.format(_path))
    _path = str(_path)  # convert unicode
    _path = _path.strip('"')

    _LOGGER.debug('ABS PATH %s', _path)
    if _path == '~':
        _path = HOME_PATH
    elif _path.startswith('~/'):
        _path = HOME_PATH+_path[1:]
    elif _path.startswith('file:///'):
        _path = _path.replace('file:///', '/', 1)
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

    # Apply map root
    _env = os.environ.get('PINI_ABS_PATH_REPLACE_ROOTS', '')
    _replace_roots = [_item.split('>>>') for _item in _env.split(';') if _item]
    _LOGGER.debug(' - REPLACE ROOTS %s', _replace_roots)
    for _find, _replace in _replace_roots:
        if _path.startswith(_find):
            _LOGGER.debug(' - REPLACE ROOT %s -> %s', _find, _replace)
            _path = _replace + _path[len(_find):]
            _LOGGER.debug(' - UPDATE %s', _path)

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


def block_on_file_system_disabled(func):
    """Block the given function from executing if file system disabled.

    Args:
        func (fn): function to block

    Returns:
        (fn): function with block installed
    """

    @functools.wraps(func)
    def _env_blocked_func(*args, **kwargs):

        if os.environ.get('PINI_DISABLE_FILE_SYSTEM'):
            raise DebuggingError(
                "Access file system disabled using PINI_DISABLE_FILE_SYSTEM")

        return func(*args, **kwargs)

    return _env_blocked_func


def copied_path():
    """Find any path copied in the paste buffer.

    This applies path mapping, and aims to remove any superfluous prefix
    that is found if you copy a path in microsoft teams.

    Returns:
        (str): copied path
    """
    from pini import pipe
    from pini.qt import QtGui

    _LOGGER.debug('COPIED PATH')
    _text = norm_path(QtGui.QClipboard().text().strip())
    _LOGGER.debug(' - TEXT %s', _text)

    if os.path.exists(_text):
        return _text

    # Try mapping path
    _text = pipe.map_path(_text, mode='any')
    if os.path.exists(_text):
        return _text

    # Try splitting by jobs root
    _LOGGER.debug(' - JOBS ROOT %s', pipe.JOBS_ROOT.path)
    if pipe.JOBS_ROOT.path in _text:
        _, _rel_path = _text.rsplit(pipe.JOBS_ROOT.path, 1)
        _path = abs_path('{}/{}'.format(pipe.JOBS_ROOT.path, _rel_path))
        if os.path.exists(_path):
            return _path

    return None


def is_abs(path):
    """Test if the given path is absolute.

    Args:
        path (str): path to test

    Returns:
        ():
    """
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
    if hasattr(_path, 'path') and isinstance(_path.path, six.string_types):
        _path = _path.path

    _path = _path.strip('"')
    try:
        _path = os.path.normpath(_path).replace('\\', '/')
    except AttributeError:
        raise ValueError(_path)

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
        _path = _path.replace('~', HOME_PATH)

    return str(_path)


def restore_cwd(func):
    """Decorator to restore the current working directory.

    Args:
        func (fn): function to decorate

    Returns:
        (fn): decorated function
    """

    @functools.wraps(func)
    def _restore_cwd_fn(*args, **kwargs):
        _cwd = os.getcwd()
        _result = func(*args, **kwargs)
        os.chdir(_cwd)
        return _result

    return _restore_cwd_fn


def search_files_for_text(
        files, text=None, filter_=None, edit=False,
        progress=True, verbose=0):
    """Search  a list of files for text.

    Args:
        files (File list): files to search
        text (str): exact text to search for
        filter_ (str): per line filter
        edit (bool): edit first match and exit
        progress (bool): show progress
        verbose (int): print process data

    Returns:
        (bool): whether search completed without matches
    """
    from pini.utils import File, passes_filter

    _found_instance = False
    _files = files
    if progress:
        from pini import qt
        _files = qt.progress_bar(_files)
    for _file in _files:

        dprint('CHECKING FILE', _file, verbose=verbose)

        _printed_path = False
        _file = File(_file)
        for _idx, _line in enumerate(_file.read().split('\n')):

            try:
                _text_in_line = text and text in _line
            except UnicodeDecodeError:
                continue

            try:
                _filter_in_line = filter_ and passes_filter(
                    _line, filter_, case_sensitive=True)
            except UnicodeDecodeError:
                continue

            # Check if this line should be printed
            _print_line = False
            if _text_in_line:
                lprint(' - MATCHED TEXT IN LINE', text, verbose=verbose)
                _print_line = True
            elif _filter_in_line:
                lprint(' - MATCHED FILTER IN LINE', filter_, verbose=verbose)
                _print_line = True

            if _print_line:
                if not _printed_path:
                    lprint(abs_path(_file))
                lprint('{:>6} {}'.format(
                    '[{:d}]'.format(_idx+1), _line.rstrip()))
                _printed_path = True
                _found_instance = True
                if edit:
                    File(_file).edit(line_n=_idx+1)
                    return False

        if _printed_path:
            lprint()

    if not _found_instance:
        dprint('No instances found')

    return True
