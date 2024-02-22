"""General release tools."""

import logging

_LOGGER = logging.getLogger(__name__)


def find_tests(mode=None, repos=(), filter_=None):
    """Find unit/integration tests.

    Args:
        mode (str): tests to find (all/unit/integration)
        repos (PRRepo list): override default list of repos
        filter_ (str): apply test name filter

    Returns:
        (PRTest list): unit/integration tests
    """
    from .. import release
    _repos = repos or [release.PINI]
    _tests = []
    for _repo in _repos:
        _tests += _repo.find_tests(mode=mode, filter_=filter_)
    return _tests


def _test_sort_key(test):
    """Sort function for release tests.

    Unit tests should be run before integration tests, and then the tests
    which have passed least recently should be run.

    Args:
        test (PRTest): release test to sort

    Returns:
        (tuple): sort key
    """
    return test.test_type != 'unit', test.last_complete_time()


def run_tests(mode='all', tests=None, force=False):
    """Run release tests.

    Args:
        mode (str): which tests to run (all/unit/integration)
        tests (PRTest list): override list of tests to run
        force (bool): lose unsaved changes without confirmation
    """
    from pini import qt, dcc

    _tests = list(tests) if tests else find_tests(mode=mode)
    _tests.sort(key=_test_sort_key)

    if not force and mode and mode.lower() != 'unit':
        dcc.handle_unsaved_changes()

    for _idx, _test in qt.progress_bar(
            enumerate(_tests, start=1), 'Running {:d} test{}',
            stack_key='RunTests'):
        _LOGGER.info('(%d/%d) RUNNING TEST %s', _idx, len(_tests), _test)
        _test.execute()
        _LOGGER.info(' - COMPLETED TEST %s', _test)
        print('')
