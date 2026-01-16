"""General tools for managing sanity checks."""

# pylint: disable=too-many-statements

import inspect
import logging
import operator
import os
import time

from pini import pipe, dcc, testing
from pini.utils import (
    passes_filter, File, PyFile, cache_result, abs_path, Dir, single,
    apply_filter, EMPTY, is_pascal)

from . import sc_check

_LOGGER = logging.getLogger(__name__)


def find_check(name=None, catch=False, **kwargs):
    """Find a single sanity check.

    Args:
        name (str): match check by name
        catch (bool): no error if fail to find test

    Returns:
        (SCCheck): matching check
    """
    _checks = find_checks(**kwargs)
    if name:
        _checks = [_check for _check in _checks if _check.name == name]
    return single(_checks, catch=catch)


def find_checks(  # pylint: disable=too-many-branches
        filter_=None, work=None, task=EMPTY, action=None, force=False):
    """Find sanity checks to apply.

    Args:
        filter_ (str): filter checks by name
        work (CPWork): override work file
        task (str): force task (otherwise current task is used) - if
            'all' is passed, no task filter is applied and all checks
            are returned
        action (str): apply action filter
            (eg. render/cache)
        force (bool): force reread checks from disk

    Returns:
        (SCCheck list): checks
    """

    # Check action
    if action and not (
            action.endswith('Publish') or
            action.endswith('Cache') or
            action.endswith('Render') or
            action in ('Blast', )):
        raise ValueError(action)
    if action and testing.dev_mode():
        assert is_pascal(action)

    _all_checks = read_checks(force=force)
    _work = work or pipe.cur_work()
    _sc_settings = _work.entity.settings['sanity_check'] if _work else {}

    # Determine task
    if task is not EMPTY:
        _task = task
    else:
        _task = _work.pini_task if _work else None
    _disable_task_filter = _task == 'all'
    if not _disable_task_filter:
        _task = pipe.map_task(_task, fmt='pini')
    _LOGGER.debug(
        'FIND CHECKS action=%s task=%s work=%action, s', action, _task, _work)

    # Filter checks based on work
    if filter_:  # Apply basic to help debugging
        _all_checks = apply_filter(
            _all_checks, filter_, key=operator.attrgetter('name'))
    _LOGGER.debug(' - FILTERING %d CHECKS', len(_all_checks))
    _checks = []
    for _check in _all_checks:

        _LOGGER.debug(' - CHECKING %s', _check)

        # Check enabled
        if not _check.enabled:
            _LOGGER.debug('   - CHECK DISBLED IN CODE')
            continue
        _settings = _sc_settings.get(_check.name, {})
        _enabled = _settings.get('enabled', _check.enabled)
        if not _enabled:
            _LOGGER.debug('   - CHECK DISBLED IN SETTINGS')
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

        # Apply action + task filters (action overrides task)
        if action and _check.action_filter:
            _LOGGER.debug('   - ACTION FILTER %s', _check.action_filter)
            if not passes_filter(action, _check.action_filter):
                _LOGGER.debug('   - REJECTED ACTION')
                continue
        else:
            if _disable_task_filter:
                pass
            elif _task is None:
                if _check.task_filter:
                    continue
            elif isinstance(_task, str):
                if not passes_filter(_task, _check.task_filter):
                    _LOGGER.debug(
                        '   - REJECTED TASK task=%s filter=%s',
                        _task, _check.task_filter)
                    continue
            else:
                raise ValueError(_task)

        _LOGGER.debug('   - ACCEPTED %s', _check)
        _checks.append(_check)

    _LOGGER.info(' - FOUND %d "%s" CHECKS', len(_checks), _task)

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
    _LOGGER.debug('CHECKING %d DIRS %s', len(_dirs), _dirs)
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
        _checks += _checks_from_py(_py)
    _LOGGER.debug(
        'FOUND %d CHECKS IN %.01fs', len(_checks), time.time() - _start)

    # Allow custom checks to replace default checks (by name)
    _map = {}
    for _check in _checks:
        _map[_check.name] = _check
    _checks = sorted(_map.values())

    return sorted(_checks)


def _checks_from_py(py_file) -> list:
    """Checks from a python file.

    Args:
        py_file (PyFile): file to read

    Returns:
        (SCCheck list): checks
    """
    _LOGGER.debug(' - PY %s', py_file.path)
    _mod = py_file.to_module(catch=True)
    if not _mod:
        _LOGGER.debug('   - FAILED TO IMPORT')
        return []

    # Search this module for sanity checks
    _members = inspect.getmembers(_mod, inspect.isclass)
    _LOGGER.debug('   - MEMS %d %s', len(_members), _members)
    _types = []
    for _, _type in _members:
        if (
                not issubclass(_type, sc_check.SCCheck) or
                _type.__name__.startswith('_')):
            _LOGGER.debug('     - REJECTED NON-CHECK %s', _type)
        _types.append(_type)
    _LOGGER.debug('   - TYPES %d %s', len(_types), _types)

    # Check these checks were defined in this py file
    _checks = []
    _class_names = [_class.name for _class in py_file.find_classes()]
    for _type in _types:
        _src = abs_path(inspect.getfile(_type))
        _src = File(_src).to_file(extn='py')
        if _src != py_file:
            _LOGGER.debug('   - REJECTED type="%s" path="%s"', _type, _src.path)
            continue
        if _type.__name__ not in _class_names:
            _LOGGER.debug('   - REJECTED MISSING NAME %s', _type.__name__)
            continue
        _check = _type()
        _checks.append(_check)

    _LOGGER.debug('   - FOUND %d CHECKS %s', len(_checks), _checks)

    return _checks
