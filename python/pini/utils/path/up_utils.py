"""General utilities for managing paths."""

# pylint: disable=anomalous-backslash-in-string

import functools
import getpass
import logging
import os
import tempfile

from ..u_error import DebuggingError
from ..u_misc import dprint, lprint

_LOGGER = logging.getLogger(__name__)


def _read_mounts():
    """Get a list of mounted drives.

    Returns:
        (str list): mounted drive root paths
    """
    _letters = [chr(_idx) for _idx in range(ord('A'), ord('Z') + 1)]
    _mounts = []
    for _letter in _letters:
        _path = _letter + ":/"
        if os.path.exists(_path):
            _mounts.append(_path)
    return _mounts


MOUNTS = _read_mounts()


def _get_home_path():
    """Get path to home dir (not including Documents dir).

    Returns:
        (str): home dir path
    """
    _LOGGER.debug('GET HOME PATH')
    _user = getpass.getuser()

    # Check for env overrides
    if 'PINI_HOME' in os.environ:
        _home = os.environ['PINI_HOME']
        _LOGGER.debug(' - USING $PINI_HOME %s', _home)
        return _home

    if 'HOME' in os.environ:
        _home = os.environ['HOME']
        _LOGGER.debug(' - APPLIED $HOME %s', _home)
    else:
        _home = os.path.expanduser("~")
        _LOGGER.debug(' - USING ~ %s', _home)
    _home = _home.replace('\\', '/')
    _LOGGER.debug(' - CLEANED %s', _home)

    # Remove Documents folder
    _dir = 'Documents'
    if _home.endswith(f'/{_dir}'):
        _home = _home[: - len(_dir) - 1]
        _LOGGER.debug(' - REMOVE DIR %s %s', _dir, _home)
        # _home = asdasd

    # Check for clean mount
    if _home.count(_user) == 1:
        _home_root, _ = _home.split(_user)
        _home_tail = _home[len(_home_root):].lstrip('/')
        _LOGGER.debug(' - CHECKING MOUNTS %s %s', _home_tail, MOUNTS)
        for _mount in MOUNTS:
            _mount_home = os.path.abspath(_mount + '/' + _home_tail)
            if os.path.exists(_mount_home):
                _home = _mount_home.replace('\\', '/')
                _LOGGER.debug(' - UPDATED TO MOUNT %s', _home)
                break

    # Strip off OneDrive (maya adds this)
    _user_home = f'C:/Users/{_user}'
    if _home.startswith(_user_home) and 'OneDrive' in _home:
        _home = _user_home
        _LOGGER.debug(' - STRIPPING OneDrive %s', _home)

    _LOGGER.debug(' - HOME %s', _home)

    return _home


HOME_PATH = _get_home_path()


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
            _user[:6] + '~1',
            _user[:6].upper() + '~1',
    ]:
        _LOGGER.debug(' - CROPPED USER %s', _cropped_user)
        if _tmp.count(_cropped_user) == 1:
            _tmp = _tmp.replace(_cropped_user, _user)

    _LOGGER.debug(' - TMP DIR %s (Z)', _tmp)
    return _tmp


TMP_PATH = _get_tmp_dir()


def error_on_file_system_disabled(path=None):
    """Throw an error if file system disabled.

    File system is disabled using $PINI_DISABLE_FILE_SYSTEM. This is
    used for debugging.

    Args:
        path (str): path that was accessed (for error message)

    Raises:
        (DebuggingError): if $PINI_DISABLE_FILE_SYSTEM applied
    """
    if os.environ.get('PINI_DISABLE_FILE_SYSTEM'):
        from pini.tools import error
        error.TRIGGERED = True
        _msg = "Access file system disabled using PINI_DISABLE_FILE_SYSTEM"
        if path:
            _msg += ' ' + path
        raise DebuggingError(_msg)


def copied_path(exists=True):
    """Find any path copied in the paste buffer.

    This applies path mapping, and aims to remove any superfluous prefix
    that is found if you copy a path in microsoft teams.

    Args:
        exists (bool): test whether path exists

    Returns:
        (str): copied path
    """
    from pini import pipe
    from pini.qt import QtGui
    from pini.utils import abs_path, norm_path

    _LOGGER.debug('COPIED PATH')
    _text = norm_path(QtGui.QClipboard().text().strip())
    _LOGGER.debug(' - TEXT "%s"', _text)

    if os.path.exists(_text):
        return _text

    # Try mapping path
    _path = pipe.map_path(_text, mode='any')
    if os.path.exists(_path):
        return _path

    # Try splitting by jobs root
    _LOGGER.debug(' - JOBS ROOT %s', pipe.ROOT.path)
    if pipe.ROOT.path in _path:
        _, _rel_path = _path.rsplit(pipe.ROOT.path, 1)
        _path = abs_path(f'{pipe.ROOT.path}/{_rel_path}')

    if not exists:
        return _path

    if os.path.exists(_path):
        return _path

    return None


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


def search_dir_files_for_text(
        dir_, text=None, filter_=None, file_filter=None, edit=False,
        extns=('py', ), encoding=None):
    """Search text in files in the given directory.

    Args:
        dir_ (str): directory to search
        text (str): exact text to search for
        filter_ (str): per line filter
        file_filter (str): file path filter
        edit (bool): edit first match and exit
        extns (tuple): file extensions to match
        encoding (str): override file encoding
    """
    from pini.utils import Dir
    _dir = Dir(dir_)
    _files = _dir.find(type_='f', filter_=file_filter, extns=extns)
    _LOGGER.info('FOUND %d FILES', len(_files))
    search_files_for_text(
        _files, text=text, filter_=filter_, edit=edit, encoding=encoding)


def search_files_for_text(
        files, text=None, filter_=None, edit=False, encoding='utf-8-sig',
        progress=True, catch=False):
    """Search  a list of files for text.

    Args:
        files (File list): files to search
        text (str): exact text to search for
        filter_ (str): per line filter
        edit (bool): edit first match and exit
        encoding (str): override file encoding
        progress (bool): show progress
        catch (bool): no error if file fails to open

    Returns:
        (bool): whether search completed without matches
    """
    _found_instance = False
    _files = files
    if progress:
        from pini import qt
        _files = qt.progress_bar(_files)
    _n_lines = _n_files = 0
    for _file in _files:

        _LOGGER.debug('CHECKING FILE %s', _file)

        # Read file contents
        try:
            _file, _body = _read_file_content(
                file_=_file, encoding=encoding, catch=catch)
        except UnicodeDecodeError:
            _LOGGER.error('UNICODE ERROR ON READ %s', _file)
            continue

        # Check file contents
        _printed_path, _n_file_lines = _search_file_contents(
            file_=_file, body=_body, text=text, filter_=filter_, edit=edit)
        _n_lines += _n_file_lines
        if _printed_path:
            _n_files += 1
            _found_instance = True

    if not _found_instance:
        dprint('No instances found')
    _LOGGER.info(' - MATCHED %d FILES / %d LINES', _n_files, _n_lines)

    return True


def _search_file_contents(file_, body, text, filter_, edit):
    """Apply search to file contents.

    Args:
        file_ (str): path to source file
        body (str): file body
        text (str): exact text to search for
        filter_ (str): per line filter
        edit (bool): edit first match and exit
    """
    from pini.utils import File, passes_filter, abs_path

    # Check line of file
    _printed_path = False
    _n_lines = 0
    for _idx, _line in enumerate(body.split('\n')):

        # Check line
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
            _LOGGER.debug(' - MATCHED TEXT IN LINE %s', text)
            _print_line = True
        elif _filter_in_line:
            _LOGGER.debug(' - MATCHED FILTER IN LINE %s', filter_)
            _print_line = True

        if _print_line:
            _n_lines += 1
            if not _printed_path:
                lprint(abs_path(file_))
            _line_s = f'[{_idx+1:d}]'
            lprint(f'{_line_s:>6} {_line.rstrip()}')
            _printed_path = True
            if edit:
                File(file_).edit(line_n=_idx + 1)
                raise StopIteration

    if _printed_path:
        lprint()

    return _printed_path, _n_lines


def _read_file_content(file_, catch, encoding):
    """Read content of the given file.

    Args:
        file_ (str): path to file to read
        catch (bool): no error if file fails to open
        encoding (str): override file encoding

    Returns:
        (File, str): file/body
    """
    from pini.utils import File
    _file = File(file_)
    try:
        return _file, _file.read(encoding=encoding)
    except UnicodeDecodeError as _exc:
        if catch:
            _LOGGER.warning(
                ' - FILE ERRORED ON READ %s %s', _file.path, _exc)
            return _file, ''
        raise _exc
