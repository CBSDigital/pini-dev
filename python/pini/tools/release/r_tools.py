"""General release tools."""


def find_tests(mode=None, repos=()):
    """Find unit/integration tests.

    Args:
        mode (str): tests to find (all/unit/integration)
        repos (PRRepo list): override default list of repos

    Returns:
        (PRTest list): unit/integration tests
    """
    from .. import release
    _repos = repos or [release.PINI]
    _tests = []
    for _repo in _repos:
        _tests += _repo.find_tests(mode=mode)
    return _tests
