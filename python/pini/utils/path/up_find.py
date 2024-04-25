"""Tools for managing the find function."""

import logging
import os

from ..u_error import DebuggingError
from ..u_misc import EMPTY

from . import up_utils

_LOGGER = logging.getLogger(__name__)


def find(path, depth=None, class_=None, type_=None, catch_missing=False,
         catch_access_error=False, base=None, filter_=None, full_path=True,
         hidden=False, extn=EMPTY, extns=None, head=None, tail=None,
         filename=None):
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
        filename (str): filter by exact filename match

    Returns:
        (str list): list of file paths
    """
    from pini.utils import File, Dir

    _LOGGER.debug('FIND %s', path)

    if os.environ.get('PINI_DISABLE_FILE_SYSTEM'):
        raise DebuggingError(
            "Read yaml disabled using PINI_DISABLE_FILE_SYSTEM")

    _dir = Dir(up_utils.abs_path(path))
    _data = _read_find_data(
        dir_=_dir, depth=depth, catch_missing=catch_missing,
        hidden=hidden, catch_access_error=catch_access_error)

    # Setup extns filter
    _extns = set(extns or [])
    if extn is not EMPTY:
        _LOGGER.debug(' - ADDING EXTN %s', extn)
        _extns.add(extn)
    _LOGGER.debug(' - EXTNS %s', _extns)

    _paths = []
    for _path, _type in _data:

        # Apply filters
        if _result_is_filtered(
                result=_path, result_type=_type, type_=type_, filter_=filter_,
                base=base, extns=_extns, head=head, tail=tail,
                filename=filename):
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

        _c_path = up_utils.abs_path(  # Clean path
            '{}/{}'.format(dir_.path, _rc_path))
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


def _result_is_filtered(  # pylint: disable=too-many-return-statements
        result, result_type, type_, filter_, base, extns, head, tail,
        filename):
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
        filename (str): filter by exact filename match

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
    if head and not _path_obj.base.startswith(head):
        return True
    if tail and not _path_obj.base.endswith(tail):
        return True
    if filename and _path_obj.filename != filename:
        return True

    return False
