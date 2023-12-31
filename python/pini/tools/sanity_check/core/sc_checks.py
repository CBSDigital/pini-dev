"""General tools for managing sanity checks."""

import inspect
import logging
import os
import time

from pini import pipe, dcc
from pini.utils import (
    passes_filter, File, PyFile, cache_result, abs_path, Dir, single)

from . import sc_check

_LOGGER = logging.getLogger(__name__)


def find_check(filter_, task=None):
    """Find a single sanity check.

    Args:
        filter_ (str): filter by name
        task (str): force task (otherwise current task is used)

    Returns:
        (SCCheck): matching check
    """
    return single(find_checks(filter_=filter_, task=task))


def find_checks(
        filter_=None, dev=False, work=None, task=None, force=False):
    """Find sanity checks to apply.

    Args:
        filter_ (str): filter checks by name
        dev (bool): add dev checks
        work (CPWork): override work file
        task (str): force task (otherwise current task is used)
        force (bool): force reread checks from disk

    Returns:
        (SCCheck list): checks
    """
    _work = work or pipe.cur_work()
    _task = pipe.map_task(
        task or (_work.task if _work else None),
        fmt='pini')
    _all_checks = read_checks(force=force)
    _LOGGER.debug('FIND CHECKS task=%s work=%s', _task, _work)

    _settings = _work.entity.settings if _work else {}
    _sc_settings = _settings.get('sanity_check', {})

    # Filter checks based on work
    _LOGGER.debug('FILTERING %d CHECKS', len(_all_checks))
    _checks = []
    for _check in _all_checks:

        _LOGGER.debug(' - CHECKING %s', _check)

        # Check enabled
        if not _check.enabled:
            _LOGGER.debug('   - CHECK NOT ENABLED')
            continue

        # Apply dev filter
        if not dev and _check.dev_only:
            _LOGGER.debug('   - DEV FILTER REJECTED')
            continue

        if not passes_filter(_check.name, filter_):
            _LOGGER.debug('   - FILTER REJECTED %s', filter_)
            continue

        # Apply dcc filter
        if not passes_filter(dcc.NAME, _check.dcc_filter):
            _LOGGER.debug('   - DCC FILTER REJECTED %s', filter_)
            continue

        # Apply profile filter
        _profile = _work.profile if _work else None
        if _check.profile_filter and not _profile:
            _LOGGER.debug('   - PROFILE FILTER REJECTED %s')
            continue
        if (
                _profile and
                not passes_filter(_profile, _check.profile_filter)):
            _LOGGER.debug(
                '   - REJECTED PROFILE profile=%s filter=%s',
                _profile, _check.profile_filter)
            continue

        # Apply task filter
        if _check.task_filter and (
                not _task or
                not passes_filter(_task, _check.task_filter)):
            _LOGGER.debug(
                '   - REJECTED TASK task=%s filter=%s',
                _task, _check.task_filter)
            continue

        # Apply settings filter
        if not _sc_settings.get(_check.name, {}).get('enabled', True):
            continue

        _LOGGER.debug('   - ACCEPTED %s', _check)
        _checks.append(_check)

    return sorted(_checks)


@cache_result
def read_checks(force=False):
    """Read checks from check directories.

    Args:
        force (bool): force reread checks from disk

    Returns:
        (SCCheck list): checks
    """
    from .. import checks

    _LOGGER.debug('READ CHECKS')
    _start = time.time()

    # Find search dirs
    _dirs = [File(checks.__file__).to_dir()]
    _env = os.environ.get('PINI_SANITY_CHECK_DIRS')
    if _env:
        _dirs += [Dir(abs_path(_path)) for _path in _env.split(';')]

    # Search dirs
    _LOGGER.debug('CHECKING %d DIRS', len(_dirs))
    _pys = []
    for _dir in _dirs:
        if not _dir.exists():
            _LOGGER.debug(' - MISSING %s', _dir.path)
            continue
        _dir_pys = [
            _py for _py in _dir.find(
                type_='f', class_=PyFile, depth=1, extn='py')
            if not _py.filename.startswith('_')]
        _LOGGER.debug(' - FOUND %d PYS IN %s', len(_dir_pys), _dir.path)
        _pys += _dir_pys
    _LOGGER.debug('PYS %d %s', len(_pys), _pys)

    # Read py files to find checks
    _checks = []
    for _py in _pys:
        _LOGGER.debug(' - PY %s', _py.path)
        _mod = _py.to_module(catch=True)
        if not _mod:
            _LOGGER.debug('   - FAILED TO IMPORT')
            continue
        _types = [
            _check for _, _check in inspect.getmembers(_mod, inspect.isclass)
            if issubclass(_check, sc_check.SCCheck) and
            not _check.__name__.startswith('_')]
        _LOGGER.debug('   - MOD %s types=%d', _mod, len(_types))
        _py_checks = []
        for _type in _types:
            _src = File(inspect.getfile(_type)).to_file(extn='py')
            if _src != _py:
                _LOGGER.debug('   - REJECTED type=%s path=%s', _type, _src.path)
                continue
            _check = _type()
            _py_checks.append(_check)
        _LOGGER.debug('   - FOUND %d CHECKS', len(_py_checks))
        _checks += _py_checks

    _LOGGER.debug('FOUND %d CHECKS IN %.01fs', len(_checks),
                  time.time() - _start)

    return sorted(_checks)
