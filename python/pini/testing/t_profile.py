"""Profiling tools."""

import cProfile
import functools
import logging
import pstats
import time

from pini.utils import TMP, File

_LOGGER = logging.getLogger(__name__)

_PROFILE = None
_PROFILE_START = None

_PROFILE_FILE_FMT = TMP.to_file('profile/{name}.prof').path
PROFILE_TXT_FMT = TMP.to_file('profile/{name}_readable.txt').path
_PROFILE_PNG_FMT = TMP.to_file('profile/{name}.png').path

PROFILE_FILE = File(_PROFILE_FILE_FMT.format(name='pini'))
PROFILE_TXT = File(PROFILE_TXT_FMT.format(name='pini'))


def profile_start():
    """Start profiler."""
    global _PROFILE, _PROFILE_START
    _PROFILE_START = time.time()
    _PROFILE = cProfile.Profile()
    _PROFILE.enable()


def profile_stop(name='pini', gprof2dot=False, bkp=True):
    """Stop profiler and write profiling information to disk.

    The data is stored in a readable form here:

    $TMP/profile/readable.txt

    It is also backed up to a timestamped file in the same directory.

    Args:
        name (str): name to apply to backup file
        gprof2dot (bool): display gprof2dot command
        bkp (bool): save profile file backup
    """
    global _PROFILE, _PROFILE_START  # pylint: disable=global-variable-not-assigned
    assert _PROFILE and _PROFILE_START

    _PROFILE.disable()

    _file = File(_PROFILE_FILE_FMT.format(name=name))
    _txt = File(PROFILE_TXT_FMT.format(name=name))

    # Dump to file
    _file.test_dir()
    _PROFILE.dump_stats(_file.path)
    _LOGGER.info('RAN PROFILE IN %.02fs', time.time() - _PROFILE_START)
    _LOGGER.info(' - WROTE FILE %s', _file.path)
    if gprof2dot:
        _png = File(_PROFILE_PNG_FMT.format(name=name))
        _LOGGER.info(' - gprof2dot -f pstats %s | dot -Tpng -o %s',
                     _file.path, _png.path)

    # Dump readable file
    _txt.test_dir()
    _hook = open(_txt.path, 'w')
    _stats = pstats.Stats(_file.path, stream=_hook)
    _stats.sort_stats('cumulative')
    _stats.print_stats()
    _LOGGER.info(' - WROTE READABLE %s', _txt.path)

    # Bkp readable file
    if bkp:
        _bkp = _txt.bkp()
        _txt.copy_to(_bkp, verbose=0)
        _LOGGER.info(' - WROTE BKP %s', _bkp.path)


def to_profiler(name='pini'):
    """Build profiler decorator.

    Args:
        name (str): override profiler name (use for filenames)

    Returns:
        (func): profiler decorator
    """

    def _exec_func_in_profile(func):

        @functools.wraps(func)
        def _profile_func(*args, **kwargs):
            profile_start()
            _result = func(*args, **kwargs)
            profile_stop(name=name)

            return _result

        return _profile_func

    return _exec_func_in_profile


def profile(func):
    """Execute the given function inside the pini profiler.

    Args:
        func (fn): function to decorate

    Returns:
        (fn): decorated function
    """
    _profiler = to_profiler()

    return _profiler(func)
