"""Tools for managing unit/integration test files."""

from pini.utils import PyFile, single

from . import r_test


class PRTestFile(PyFile):
    """Represents a test file containing unit/integration tests."""

    def __init__(self, file_):
        """Constructor.

        Args:
            file_ (str): path to test file
        """
        super(PRTestFile, self).__init__(file_)

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

    def find_tests(self):
        """Find unit/integration tests in this file.

        Returns:
            (PRTest list): unit/integration tests
        """
        _tests = []
        for _class in self.find_classes():
            for _def in _class.find_defs():
                if _def.clean_name == 'setUp':
                    continue
                _test = r_test.PRTest(
                    method=_def, class_=_class, py_file=self)
                _tests.append(_test)
        return _tests
