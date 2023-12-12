"""Profiling tools."""

import cProfile
import functools
import logging
import pstats
import time

from pini.utils import TMP, strftime

_LOGGER = logging.getLogger(__name__)

_PROFILE = None
_PROFILE_START = None
PROFILE_FILE = TMP.to_file('pini.profile')
PROFILE_TXT = TMP.to_file('profile/readable.txt')


def profile(func):
    """Execute the given function inside the pini profiler.

    Args:
        func (fn): function to decorate

    Returns:
        (fn): decorated function
    """

    @functools.wraps(func)
    def _profile_func(*args, **kwargs):
        profile_start()
        _result = func(*args, **kwargs)
        profile_stop(name=func.__name__)

        return _result

    return _profile_func


def profile_start():
    """Start profiler."""
    global _PROFILE, _PROFILE_START
    _PROFILE_START = time.time()
    _PROFILE = cProfile.Profile()
    _PROFILE.enable()


def profile_stop(name='profile'):
    """Stop profiler and write profiling information to disk.

    The data is stored in a readable form here:

    $TMP/profile/readable.txt

    It is also backed up to a timestamped file in the same directory.

    Args:
        name (str): name to apply to backup file
    """
    global _PROFILE, _PROFILE_START  # pylint: disable=global-variable-not-assigned
    assert _PROFILE and _PROFILE_START

    _PROFILE.disable()

    # Dump to file
    _png = TMP.to_file('pini_profile.png')
    _PROFILE.dump_stats(PROFILE_FILE.path)
    _LOGGER.info('RAN PROFILE IN %.02fs', time.time() - _PROFILE_START)
    _LOGGER.info(' - WROTE FILE %s', PROFILE_FILE.path)
    _LOGGER.info(' - gprof2dot -f pstats %s | dot -Tpng -o %s',
                 PROFILE_FILE.path, _png.path)

    # Dump readable file
    PROFILE_TXT.test_dir()
    _hook = open(PROFILE_TXT.path, 'w')
    _stats = pstats.Stats(PROFILE_FILE.path, stream=_hook)
    _stats.sort_stats('cumulative')
    _stats.print_stats()
    _LOGGER.info(' - WROTE READABLE %s', PROFILE_TXT.path)

    # Bkp readable file
    _bkp = TMP.to_file(
        'profile/{}_{}.txt'.format(strftime('%y%m%d_%H%M%S'), name))
    PROFILE_TXT.copy_to(_bkp)
    _LOGGER.info(' - WROTE BKP %s', _bkp.path)
