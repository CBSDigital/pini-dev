"""General tools relating to work file elements."""

import logging

from pini import dcc, icons, pipe
from pini.utils import abs_path, HOME, install_callback

from ...cp_utils import map_path

_LOGGER = logging.getLogger(__name__)

RECENT_WORK_YAML = HOME.to_file(f'.pini/{dcc.NAME}_recent_work.yml')


def add_recent_work(work):
    """Add work file to list of recent work.

    Args:
        work (CPWork): work file to add
    """
    _v000 = work.to_work(ver_n=0)
    _recent = recent_work()
    _recent.insert(0, _v000)

    _paths = []
    for _work in _recent:
        _path = str(_work.path)
        if _path in _paths:
            continue
        _paths.append(_path)
    _paths = _paths[:20]

    RECENT_WORK_YAML.write_yml(_paths, force=True)


def cur_work(work_dir=None, catch=True):
    """Get a work file object for the current scene.

    Args:
        work_dir (CPWorkDir): force parent work dir (to faciliate caching)
        catch (bool): no error if no current work found

    Returns:
        (CPWork|None): current work (if any)
    """
    _file = dcc.cur_file()
    if not _file:
        return None
    _file = abs_path(_file)
    try:
        return pipe.CPWork(_file, work_dir=work_dir)
    except (ValueError, TypeError) as _exc:
        if not catch:
            raise ValueError('No current work') from _exc
        return None


def install_set_work_callback(callback):
    """Install callback to be applied on set work.

    Args:
        callback (fn): callback to execute on set work
    """
    from pini.tools import release
    release.apply_deprecation('11/03/25', 'Use pini.utils.install_callback')
    install_callback('SetWork', callback)


def load_recent():
    """Load most recent work file."""
    from pini import qt
    _latest = recent_work()[0].find_latest()
    qt.ok_cancel(
        'Load latest work file?\n\n' + _latest.path,
        title='Load recent', icon=icons.find('Monkey Face'))
    _latest.load()


def recent_work():
    """Read list of recent work file.

    The newest is at the front of the list.

    Returns:
        (CPWork list): recent work files
    """
    _LOGGER.debug('RECENT WORK %s', RECENT_WORK_YAML.path)
    _LOGGER.debug(' - WORK %s', pipe.CPWork)

    _paths = RECENT_WORK_YAML.read_yml(catch=True) or []
    _works = []
    for _path in _paths:
        _LOGGER.debug(' - ADD PATH %s', _path)
        try:
            _work = pipe.CPWork(_path)
        except ValueError:
            _LOGGER.debug(' - REJECTED %s', _path)
            continue
        _works.append(_work)
    return _works


def to_work(file_, catch=True):
    """Build a work file from the given path.

    Args:
        file_ (str): path to work file
        catch (bool): no error if file doesn't create valid work file

    Returns:
        (CPWork): work file
    """
    _LOGGER.debug('TO WORK %s', file_)

    if isinstance(file_, pipe.CPWork):
        return file_
    if file_ is None:
        if catch:
            return None
        raise ValueError

    _file = map_path(file_)
    _LOGGER.debug(' - FILE %s', _file)
    try:
        return pipe.CPWork(_file)
    except ValueError as _exc:
        _LOGGER.debug(' - FAILED TO MAP %s', _exc)
        if catch:
            return None
        raise _exc
