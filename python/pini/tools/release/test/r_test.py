"""Tools for managing unit/integration tests."""

import logging
import time
import unittest

from pini.utils import (
    cache_method_to_file, build_cache_fmt, to_pascal, nice_age)

_LOGGER = logging.getLogger(__name__)


class PRTest:
    """Represents a unit/integration test."""

    def __init__(self, method, class_, py_file):
        """Constructor.

        Args:
            method (PyDef): this test's method
            class_ (PyClass): this test's parent class
            py_file (PyFile): this test's parent python file
        """
        self.method = method
        self.clean_name = method.clean_name
        self.name = method.name

        self.class_ = class_
        self.py_file = py_file
        self.test_type = py_file.test_type

    @property
    def cache_fmt(self):
        """Obtain format for cache files for this test.

        Returns:
            (str): cache format
        """
        _path = '_'.join([
            self.py_file.dir + '/' + to_pascal(self.py_file.base),
            self.class_.name, to_pascal(self.method.clean_name)])
        _LOGGER.debug(' - NAME %s', self.name)
        _cache_fmt = build_cache_fmt(
            path=_path, mode='home', tool='Release', extn='pkl', dcc_=True)
        _LOGGER.debug(' - CACHE FMT %s', _cache_fmt)
        return _cache_fmt

    def edit(self):
        """Edit this test in a text editor."""
        self.method.edit()

    def execute(self):
        """Execute this test."""
        from pini.tools import error

        error.TRIGGERED = False
        _start = time.time()
        _last_exec_dur = self.last_exec_dur()
        _last_complete_time = self.last_complete_time()

        # Print header
        _title = f'------------- EXECUTE {self} -------------'
        print('\n' + '-' * len(_title))
        print(_title)
        print('-' * len(_title) + '\n')

        # Locate test method
        if _last_exec_dur and _last_complete_time:
            _age = time.time() - _last_complete_time
            _LOGGER.info(
                ' - LAST EXEC DUR %.00fs (%s AGO)', _last_exec_dur,
                nice_age(_age))
        _LOGGER.info(' - PY FILE %s', self.py_file.path)
        _mod = self.py_file.to_module(reload_=True)
        _LOGGER.info(' - REL PATH %s.py', '/'.join(_mod.__name__.split('.')))
        _case = getattr(_mod, self.class_.name)
        _LOGGER.info(' - CASE %s', _case)
        assert issubclass(_case, unittest.TestCase)
        _test = _case.__dict__[self.clean_name]

        # Build test runner
        _suite = unittest.TestSuite()
        _suite.addTest(_case(_test.__name__))
        _runner = unittest.TextTestRunner(failfast=True)

        # Run test
        _result = _runner.run(_suite)
        _LOGGER.info(' - RESULT %s %s', _result, type(_result))
        self._check_for_fail(result=_result)
        self._reset_env()

        # Write execution stats to cache
        _dur = time.time() - _start
        self.last_exec_dur(exec_dur=_dur, force=True)
        self.last_complete_time(complete_time=time.time(), force=True)

        # Print tail
        _tail = f'---------- COMPLETE {self} ({_dur:.01f}s) ----------'
        print('\n' + '-' * len(_tail))
        print(_tail)
        print('-' * len(_tail) + '\n')

    def _check_for_fail(self, result):
        """Handle test has failed.

        Args:
            result (TextTestResult): test result
        """
        from pini import qt, testing
        from pini.tools import error

        # Handle test failed
        _issues = result.errors + result.failures
        for _class, _traceback in _issues:
            _msg = _traceback.strip().split('\n')[-1]
            _LOGGER.info('[error] %s', _class)
            _LOGGER.info('[msg] %s', _msg)
            print()
            print('-----------------------------------------------')
            print('--------------- TRACEBACK (START) -------------')
            print('-----------------------------------------------')
            print(_traceback)
            print('-----------------------------------------------')
            print('---------------- TRACEBACK (END) --------------')
            print('-----------------------------------------------')
            print()
            _err = error.error_from_str(_traceback)
            testing.enable_file_system(True)
            error.launch_ui(error=_err)
            raise qt.DialogCancelled

        assert not error.TRIGGERED

    def _reset_env(self):
        """Reset testing environment."""
        from pini import pipe
        if pipe.MASTER == 'shotgrid':
            from pini.pipe import shotgrid
            shotgrid.to_handler().requests_limit = 0

    @cache_method_to_file
    def last_exec_dur(self, exec_dur=None, force=False):
        """Obtain duration of last successful execution of this test.

        Args:
            exec_dur (float): force execution time to write to cache
            force (bool): force update cache

        Returns:
            (float): duration of last execution
        """
        return exec_dur

    @cache_method_to_file
    def last_complete_time(self, complete_time=0, force=False):
        """Obtain time of last successful completion of this test.

        Args:
            complete_time (float): completion time to write to cache
            force (bool): force update cache

        Returns:
            (float): time of last successful execution
                (in seconds since epoch)
        """
        return complete_time or time.time()

    def __repr__(self):
        _type = type(self).__name__
        _type_chr = self.test_type[0].upper()
        return f'<{_type}({_type_chr}):{self.name}>'
