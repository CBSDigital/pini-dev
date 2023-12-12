"""General utilities for managing paths."""

# pylint: disable=anomalous-backslash-in-string

import functools
import getpass
import logging
import os
import tempfile

import six

from ..u_error import DebuggingError
from ..u_misc import dprint, lprint, EMPTY

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


def _read_find_data(
        dir_, depth, hidden, catch_missing=False, catch_access_error=False):
    """Read find data for the given path.

    Args:
        dir_ (Dir): dir to search in
        depth (int): limit depth of search (subdir depth)
        hidden (bool): include hidden files/dirs
        catch_missing (bool): no error if path does not exist
        catch_access_error (bool): no error on access denied

    Returns:
        ((str, char) list): list of path/type data of dir contents
    """
    from pini.utils import check_heart, Dir

    check_heart()

    _data = []

    _LOGGER.debug('READ FIND DATA %s', dir_.path)
    if not dir_.exists():
        if catch_missing:
            return _data
        raise OSError('Missing dir '+dir_.path)

    # Decrement depth
    _depth = depth
    if isinstance(_depth, int):
        _depth = _depth - 1
    assert _depth is None or _depth >= 0
    _LOGGER.debug(' - DEPTH %s', _depth)

    # Read contents
    try:
        _rc_paths = os.listdir(dir_.path)
    except OSError as _exc:
        if not catch_access_error:
            raise _exc
        _rc_paths = []
    for _rc_path in _rc_paths:  # Got through relative paths

        if not hidden and _rc_path.startswith('.'):
            continue

        _c_path = abs_path('{}/{}'.format(dir_.path, _rc_path))  # Clean path
        _LOGGER.debug(' - TESTING %s %s', _rc_path, _c_path)

        # Read type
        _type = None
        if os.path.isdir(_c_path):
            _type = 'd'
        elif os.path.isfile(_c_path):
            _type = 'f'
        else:
            _LOGGER.warning('Unrecognised file %s', _c_path)
            continue
        _LOGGER.debug('   - TYPE %s', _type)

        # Apply recursion (must happen before filters
        if _depth != 0 and _type == 'd':
            _LOGGER.debug('   - CHECKING CHILDREN')
            _data += _read_find_data(
                dir_=Dir(_c_path), depth=_depth, hidden=hidden,
                catch_access_error=catch_access_error)

        _data.append((_c_path, _type))

    return _data


def find(path, depth=None, class_=None, type_=None, catch_missing=False,
         catch_access_error=False, base=None, filter_=None, full_path=True,
         hidden=False, extn=EMPTY, extns=None, head=None, tail=None):
    """Search for files within the given directory.

    This is aimed to mimic the behaviour of the linux/bash find command.

    Args:
        path (str): path to search in
        depth (int): maxiumum search depth
        class_ (class|True): typecast results to the given class, or
            if True return File/Dir objects
        type_ (char): filter results by type (d/f)
        catch_missing (bool): no error if path does not exist
        catch_access_error (bool): no error on access denied
        base (str): filter by exact file basename
            ie. bl will not match blah.txt, you'd need to use blah
        filter_ (str): apply filter string (eg. -jpg to ignore jpgs)
        full_path (bool): return full path (on by default)
        hidden (bool): include hidden files/dirs
        extn (str): filter by extension
        extns (str list): filter by list of extensions
        head (str): filter by start of filename
        tail (str): filter by end of filename

    Returns:
        (str list): list of file paths
    """
    from pini.utils import File, Dir

    _LOGGER.debug('FIND %s', path)

    if os.environ.get('PINI_DISABLE_FILE_SYSTEM'):
        raise DebuggingError(
            "Read yaml disabled using PINI_DISABLE_FILE_SYSTEM")

    _dir = Dir(abs_path(path))
    _data = _read_find_data(
        dir_=_dir, depth=depth, catch_missing=catch_missing,
        hidden=hidden, catch_access_error=catch_access_error)

    # Setup extns filter
    _extns = set(extns or [])
    if extn is not EMPTY:
        _extns.add(extn)
    _LOGGER.debug(' - EXTNS %s', _extns)

    _paths = []
    for _path, _type in _data:

        # Apply filters
        if _result_is_filtered(
                result=_path, result_type=_type, type_=type_, filter_=filter_,
                base=base, extns=_extns, head=head, tail=tail):
            _LOGGER.debug(' - FILTERED')
            continue

        if not full_path:
            _path = _dir.rel_path(_path)

        # Class filter
        if class_:
            _class = class_
            if _class is True:
                _class = {'f': File,
                          'd': Dir}[_type]
            try:
                _path = _class(_path)
            except ValueError:
                continue

        _paths.append(_path)

    return sorted(_paths)


def _result_is_filtered(  # pylint: disable=too-many-return-statements
        result, result_type, type_, filter_, base, extns, head, tail):
    """Check if the filters should remove the given path result.

    Args:
        result (str): path to result
        result_type (str): result type (d/f)
        type_ (str): type filter
        filter_ (str): string filter
        base (str): basename filter
        extns (str list): list of extensions to allow
        head (str): filename head filter
        tail (str): filename tail filter

    Returns:
        (bool): whether result should be filtered
    """
    from pini.utils import passes_filter, Path

    if type_ and result_type != type_:
        return True
    if filter_ and not passes_filter(result, filter_):
        return True

    _path_obj = Path(result)
    if base and _path_obj.base != base:
        _LOGGER.debug(
            ' - BASE FILTERED base=%s filter=%s', _path_obj.base, base)
        return True
    if extns and _path_obj.extn not in extns:
        return True
    if head and not _path_obj.filename.startswith(head):
        return True
    if tail and not _path_obj.filename.endswith(tail):
        return True

    return False


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
