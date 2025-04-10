"""General release tools."""

import logging
import operator
import os
import time
import sys

from pini.utils import single, apply_filter

_LOGGER = logging.getLogger(__name__)


def find_test(match):
    """Find a unit/integration test.

    Args:
        match (str): token to match to test (eg. name, clean name)

    Returns:
        (PRTest): matching test
    """
    _tests = find_tests()

    # Try exact name match
    _name_match = single(
        [_test for _test in _tests if match in (_test.name, _test.clean_name)],
        catch=True)
    if _name_match:
        return _name_match

    # Try filter match
    _filter_match = single(
        apply_filter(_tests, match, key=operator.attrgetter('name')),
        catch=True)
    if _filter_match:
        return _filter_match

    raise ValueError(match)


def find_tests(mode=None, repos=(), filter_=None):
    """Find unit/integration tests.

    Args:
        mode (str): tests to find (all/unit/integration)
        repos (PRRepo list): override default list of repos
        filter_ (str): apply test name filter

    Returns:
        (PRTest list): unit/integration tests
    """
    from ... import release
    _repos = repos or release.REPOS
    _LOGGER.debug('FIND TESTS %s', _repos)
    _tests = []
    for _repo in _repos:
        _r_tests = _repo.find_tests(mode=mode, filter_=filter_)
        _LOGGER.debug(' - %s FOUND %d TESTS', _repo, len(_r_tests))
        _tests += _r_tests
    _tests.sort(key=to_test_sort_key)
    return _tests


def to_test_sort_key(test, mode='sca/dur'):
    """Sort function for release tests.

        MCA - modulo completed age
        SCA - stepped completed age

    Aims to run the tests that were passes least recently first (at ten
    minute age steps), and then sorted with fastest tests first.

    Args:
        test (PRTest): release test to sort
        mode (str): sort mode

    Returns:
        (tuple): sort key
    """
    if mode == 'sca/dur':
        _c_time = test.last_complete_time()
        _c_age = time.time() - _c_time
        if _c_age < 0:
            raise RuntimeError(test)
        _dur = test.last_exec_dur()
        if _dur is None:
            return -sys.maxsize, 0
        _mod_c_age = _c_age % (10 * 60)
        _stepped_c_age = int(_c_age - _mod_c_age)
        _key = -_stepped_c_age, round(_dur, 2)
    elif mode == 'completed':
        _key = test.last_complete_time()
    elif mode == 'type/completed':
        _key = test.test_type != 'unit', test.last_complete_time()
    else:
        raise ValueError(mode)
    return _key


def run_tests(mode='all', tests=None, safe=True, force=False):
    """Run release tests.

    Args:
        mode (str): which tests to run (all/unit/integration)
        tests (PRTest list): override list of tests to run
        safe (bool): check environment is clean before running tests
        force (bool): lose unsaved changes without confirmation
    """
    from pini import qt, dcc, testing

    if safe:
        assert not os.environ.get('PINI_PIPE_CFG_PATH')

    testing.enable_file_system(True)
    testing.check_test_paths(force=force)

    _tests = list(tests) if tests else find_tests(mode=mode)
    _tests.sort(key=to_test_sort_key)

    # Handle unsaved changes
    if not force:
        if mode != 'unit':
            dcc.handle_unsaved_changes()
        elif mode in ('integration', 'all'):
            pass
        else:
            raise ValueError(mode)

    # Run tests
    _pos = dcc.get_main_window_ptr().geometry().center() + qt.to_p(0, -200)
    for _idx, _test in qt.progress_bar(
            enumerate(_tests, start=1), 'Running {:d} test{}', pos=_pos,
            stack_key='RunTests', show=len(_tests) > 1):
        _LOGGER.info('(%d/%d) RUNNING TEST %s', _idx, len(_tests), _test)
        _test.execute()
        _LOGGER.info(' - COMPLETED TEST %s', _test)
        print('')
