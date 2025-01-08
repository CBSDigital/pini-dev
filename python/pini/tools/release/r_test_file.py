"""Tools for managing unit/integration test files."""

import logging

from pini.utils import PyFile, single, passes_filter

from . import r_test

_LOGGER = logging.getLogger(__name__)


class PRTestFile(PyFile):
    """Represents a test file containing unit/integration tests."""

    def __init__(self, file_):
        """Constructor.

        Args:
            file_ (str): path to test file
        """
        super().__init__(file_)

        if '/integration/' in self.path:
            self.test_type = 'integration'
        elif '/unit/' in self.path:
            self.test_type = 'unit'
        else:
            raise ValueError(self.path)

        if 'nuke' in self.path:
            self.dcc_ = 'nuke'
        elif 'maya' in self.path:
            self.dcc_ = 'maya'
        else:
            self.dcc_ = None

    def find_test(self, match):
        """Find a unit/integration test.

        Args:
            match (str): match by name

        Returns:
            (PRTest): unit/integration test
        """
        _tests = self.find_tests()

        _name_test = single([
            _test for _test in _tests
            if _test.clean_name == match])
        if _name_test:
            return _name_test

        raise ValueError(match)

    def find_tests(self, filter_=None, strict=True):
        """Find unit/integration tests in this file.

        Args:
            filter_ (str): apply test name filter
            strict (bool): check test naming

        Returns:
            (PRTest list): unit/integration tests
        """
        from pini import pipe
        _LOGGER.debug('FIND TESTS %s', self)
        _tests = []
        _mod = self.to_module()
        assert _mod
        for _p_class in self.find_classes():

            # Check for pipe master filter
            _m_class = getattr(_mod, _p_class.name)
            _pipe_master_filter = getattr(
                _m_class, 'pipe_master_filter', None)
            _LOGGER.debug(' - CLASS %s %s', _p_class, _pipe_master_filter)
            if not passes_filter(pipe.MASTER, _pipe_master_filter):
                _LOGGER.debug('   - REJECTED')
                continue

            # Read tests
            for _def in _p_class.find_defs():
                if _def.clean_name == 'setUp':
                    continue
                if not passes_filter(_def.clean_name, filter_):
                    continue
                _test = r_test.PRTest(
                    method=_def, class_=_p_class, py_file=self)
                if strict and not _test.clean_name.startswith('test'):
                    _test.edit()
                    raise RuntimeError(f'Bad test name {self}')
                _tests.append(_test)

        return _tests
