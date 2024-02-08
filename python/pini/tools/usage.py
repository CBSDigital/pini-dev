"""Tools for tracking tool usage.

This module provides a decorator which will log each time a function
is used to a centralised yml file. These files are generated per day
and per user.
"""

import functools
import logging
import os
import platform
import sys
import time

import pini

from pini import dcc
from pini.utils import (
    File, Dir, cache_result, strftime, assert_eq, is_pascal, get_user,
    read_func_kwargs, Seq, to_camel)

_SESSION_START = time.time()
_LOGGER = logging.getLogger(__name__)
ROOT = os.environ.get('PINI_USAGE_DIR')
TIME_ZONE_MAP = {
    'Eastern Standard Time': 'EST',
    'Pacific Standard Time': 'PST',
    'Pacific Daylight Time': 'PDT',
}


def get_tracker(name=None, write_after=False, args=None):
    """Get usage tracking decorator.

    Args:
        name (str): override function name
        write_after (bool): write to log after execute - this allows
            the scene file to be recorded in the case of a scene load
        args (str list): list of args to read and track values of

    Returns:
        (fn): usage tracking decorator
    """
    if name:
        assert is_pascal(name)

    def _track_decorator(func):

        @functools.wraps(func)
        def _track_usage_func(*fn_args, **fn_kwargs):

            _LOGGER.debug(
                'RUNNING USAGE TRACKED FUNC %s %s', fn_args, fn_kwargs)

            # Read args
            _args = {}
            if args:
                assert isinstance(args, (list, tuple))
                _LOGGER.debug(' - ADDING ARGS %s', args)
                _kwargs = read_func_kwargs(
                    func=func, args=fn_args, kwargs=fn_kwargs)
                _LOGGER.debug(' - KWARGS %s', _kwargs)
                for _arg in args:
                    _val = _kwargs[_arg]
                    if isinstance(_val, (File, Seq)):
                        _val = _val.path
                    _args[_arg] = _val
                _LOGGER.debug(' - ADDING ARGS %s', _args)

            if write_after:
                _result = func(*fn_args, **fn_kwargs)
            if not dcc.batch_mode():
                try:
                    log_usage_event(name or func.__name__, args=_args)
                except Exception as _exc:  # pylint: disable=broad-exception-caught
                    _LOGGER.info(
                        'WRITE USAGE FAILED "%s" (%s)', _exc, type(_exc))
            if not write_after:
                _result = func(*fn_args, **fn_kwargs)

            return _result

        return _track_usage_func

    return _track_decorator


def track(func):
    """Track usage of the given function.

    Args:
        func (fn): function to track usage of

    Returns:
        (fn): usage tracked function
    """
    return get_tracker()(func)


def _build_data(func, args=None):
    """Build data dictionary to write to disk.

    Args:
        func (str): name of function being tracked
        args (dict): args data to store

    Returns:
        (dict): usage data
    """
    _data = {}

    # Basic data
    _data['func'] = func
    _data['time'] = int(time.time())
    _data['session'] = get_session_dur()
    _data['scene'] = dcc.cur_file()
    _data['machine'] = platform.node()
    _data['dcc'] = dcc.NAME
    _data['dcc_version'] = dcc.to_version(str)
    _data['platform'] = sys.platform
    if args:
        _data['args'] = args

    # Add timezone
    _zone = time.tzname[time.localtime().tm_isdst]
    _data['timezone'] = TIME_ZONE_MAP.get(_zone, _zone)

    # Add repos
    _data['repos'] = {}
    for _mod_name, _ver in _TRACKED_MODS.items():
        _data['repos'][_mod_name] = _ver.string

    return _data


def _get_usage_yml():
    """Obtain path to current usage yaml file.

    Returns:
        (File): usage yaml
    """
    _user = get_user()
    _date = strftime('%y%m%d')

    # Use $PINI_USAGE_FMT
    _fmt = os.environ.get('PINI_USAGE_FMT')
    if _fmt:
        return File(_fmt.format(user=_user, date=_date))

    # Use $PINI_USAGE_DIR
    if ROOT:
        return Dir(ROOT).to_subdir(_user).to_file(_date+'.yml')

    _LOGGER.debug(' - ROOT NOT SET')
    return None


def log_usage_event(func, args=None):
    """Write function usage instance to file.

    Args:
        func (str): name of function which was used
        args (dict): args data to store
    """
    _LOGGER.debug('WRITE USAGE TO DISK args=%s', args)

    _yml = _get_usage_yml()
    if not _yml:
        _LOGGER.debug(' - NO YML FOUND')
        return
    _LOGGER.debug(' - SET YML %s', _yml)

    _data = _build_data(func=func, args=args)
    _LOGGER.debug(' - SET DATA %s', _data)

    _yml.write_yml([_data], mode='a')
    _LOGGER.debug(' - WROTE YML')


def add_tracked_mod(mod, ver=None):
    """Add tracked module.

    This assumes the module is in a repo with a python dir and
    a correctly formatted CHANGELOG to read version from.

    The current version of this module's repo will then be
    tracked and written to file each time a usage.track decorated
    function is called.

    Args:
        mod (mod): module to track
        ver (PRVersion): override version
    """
    global _TRACKED_MODS  # pylint: disable=global-variable-not-assigned
    _ver = ver or _read_mod_ver(mod)
    _TRACKED_MODS[mod.__name__] = _ver
    _LOGGER.debug('ADDING TRACKED MOD %s %s %s', mod.__name__,
                  _ver, _TRACKED_MODS)


def get_mod_vers():
    """Get tracked module versions.

    Returns:
        (str/PRVersion list): module/version list
    """
    _vers = []
    for _mod in sorted(_TRACKED_MODS):
        _vers.append((_mod, _TRACKED_MODS[_mod]))
    return _vers


def get_session_dur():
    """Get current session duration.

    Returns:
        (int): session time in seconds
    """
    return int(time.time() - _SESSION_START)


@cache_result
def _read_mod_ver(mod, force=False):
    """Read release version of the given module.

    Args:
        mod (mod): to read
        force (bool): force reread module from CHANGELOG

    Returns:
        (PRVersion): release version
    """
    _LOGGER.debug('READ MOD VER %s', mod)
    from pini.tools import release

    # Check for env override to get mod dir
    _mod_env = 'PINI_USAGE_{}_REPO_ROOT'.format(to_camel(mod.__name__).upper())
    _LOGGER.debug(' - MOD ENV %s', _mod_env)
    if _mod_env in os.environ:

        _repo_root = os.environ[_mod_env]

    else:
        _mod_file = os.environ.get(_mod_env, mod.__file__)
        _LOGGER.debug(' - MOD FILE %s', _mod_file)

        _mod_dir = File(_mod_file).to_dir()
        assert_eq(_mod_dir.filename, mod.__name__)
        _py_dir = _mod_dir.to_dir()
        assert _py_dir.filename == 'python'
        _repo_root = _py_dir.to_dir().path

    # Read version from repo
    _LOGGER.debug(' - REPO ROOT %s', _repo_root)
    _repo = release.PRRepo(_repo_root)
    _LOGGER.debug(' - REPO %s %s', _repo, _repo.version)

    return _repo.version


_TRACKED_MODS = {pini.__name__: _read_mod_ver(pini)}
