"""Tools for managing the check file object."""

import ast
import logging
import os
import re
import time

from pini import qt
from pini.utils import (
    File, PyFile, find_exe, system, get_method_to_file_cacher, MetadataFile,
    PyDef, PyClass, abs_path, to_str, cache_result, merge_dicts,
    passes_filter, to_time_f, nice_age)

from . import r_docs, r_issue, r_autofix

DIR = File(__file__).to_dir()

_LOGGER = logging.getLogger(__name__)
_PYLINT_RC = DIR.to_file('pylint.rc')


class CheckFile(MetadataFile):
    """Represents a file being released."""

    cache_loc = 'home'
    cache_namespace = 'release'

    def apply_checks(
            self, pylint=True, pycodestyle=True, force=False):
        """Apply release checks.

        Args:
            pylint (bool): apply pylint checks
            pycodestyle (bool): apply pycodestyle checks
            force (bool): force regenerate checks data
        """
        if self.has_passed_checks():
            return
        qt.close_all_progress_bars(
            filter_='PylintCheckFile PycodestyleCheckFile')

        # Run checks
        print()
        _LOGGER.info('CHECKING FILE %s', self)
        _LOGGER.info(' - FILENAME %s', self.filename)
        _LOGGER.info(' - CACHE FMT %s', self.cache_fmt)
        if self._is_empty():
            _LOGGER.info(' - IGNORING EMPTY FILE')
        else:
            _prog = qt.progress_dialog(
                'Checking file', stack_key='CheckFile')
            self.apply_docs_check()
            _prog.set_pc(20)
            self.apply_autofix()
            _prog.set_pc(40)
            self.apply_simple_checks()
            _prog.set_pc(50)
            self.apply_deprecation_check()
            _prog.set_pc(60)
            if pylint:
                self.apply_pylint_check(force=force)
            _prog.set_pc(80)
            if pycodestyle:
                self.apply_pycodestyle_check(force=force)
            _prog.set_pc(100)
            _LOGGER.info(' - ALL CHECKS PASSED')

        # Mark as checked
        self.has_passed_checks(True, force=True)

    def _is_empty(self):
        """Test whether this file is empty.

        ie. whether it contains no meaningful code (comments are ignored).

        Returns:
            (bool): whether this is an empty file
        """
        assert self.extn in (None, 'py')
        _py = PyFile(self, check_extn=False)
        _ast = _py.to_ast()
        return not bool([
            _item for _item in _ast.body if not isinstance(_item, ast.Expr)])

    def apply_autofix(self, force=False):
        """Apply autofixes.

        Args:
            force (bool): apply updates without confirmation
        """
        r_autofix.apply_autofix(self, force=force)

    def apply_docs_check(self):
        """Apply docstrings checks."""
        _is_test = '/tests/' in self.path
        if _is_test:
            return
        if self.filename == '__init__.py' and not self.read():
            return

        assert self.extn in ('py', None)
        _py = PyFile(self, check_extn=False)

        r_docs.check_mod_docs(_py)

        for _item in _py.find_children():
            if isinstance(_item, PyDef):
                r_docs.check_def_docs(_item)
            elif isinstance(_item, PyClass):
                r_docs.check_class_docs(_item)
                for _method in _item.find_defs():
                    r_docs.check_def_docs(_method)
            else:
                raise ValueError(_item)

    def apply_deprecation_check(self):
        """Check for deprecated code.

        Any deprecations older than half a year should be removed.
        """
        if abs_path(__file__) == self.path:
            return
        for _line in self.read_lines():
            if 'release.apply_deprecation(' in _line:
                _LOGGER.info('FOUND DEPRECATION')
                _line = _line.strip()
                _LOGGER.info(' - LINE %s', _line)
                assert _line.startswith('release.apply_deprecation(')
                _date_s = re.split('["\']', _line)[1]
                _LOGGER.info(' - DATE S %s', _date_s)
                _age = time.time() - to_time_f(_date_s)
                _LOGGER.info(' - AGE %s', nice_age(_age))
                if _age > 60 * 60 * 24 * 7 * 25:
                    raise NotImplementedError

    def apply_pycodestyle_check(self, force=False):
        """Apply pycodestyle checks.

        Args:
            force (bool): force regenerate checks data
        """
        _reading = self.to_pycodestyle_reading(force=force)
        _issues = r_issue.to_pycodestyle_issues(_reading)
        _LOGGER.info('FOUND %d pycodestyle ISSUES', len(_issues))
        for _issue in qt.progress_bar(
                _issues, 'Checking {:d} pycodestyle issue{}',
                stack_key="PycodestyleCheckFile"):
            _LOGGER.info(' - ISSUE %s %s', _issue, _issue.desc)
            raise _issue.to_error(self)
        _LOGGER.info(' - PYCODESTYLE SUCCESFUL %s', self.path)

    def apply_pylint_check(self, force=False):
        """Apply pylint checks.

        Args:
            force (bool): force regenerate checks data
        """
        self._batch_apply_pylint_unused_imports()

        _issues = self.find_pylint_issues(force=force)
        _LOGGER.debug('FOUND %d pylint ISSUES', len(_issues))

        for _issue in qt.progress_bar(
                _issues, 'Checking {:d} pylint issue{}',
                stack_key="PylintCheckFile"):
            _LOGGER.info(' - ISSUE %s %s %s', _issue, _issue.name, _issue.desc)
            _LOGGER.info(' - DISABLE # pylint: disable=%s', _issue.name)
            raise _issue.to_error(self)
        _LOGGER.debug(' - LINT SUCCESFUL %s', self.path)

    def apply_simple_checks(self):
        """Apply simple checks."""
        from pini.tools import error

        _disable = _obt_cfg()['disable_checks']
        _too_long_filter = _disable.get('C0301', None)
        _check_line_len = (
            not self.is_test() and
            not passes_filter(self.path, _too_long_filter))
        _LOGGER.info(
            ' - CHECK LINE LEN %d %s', _check_line_len, _too_long_filter)

        for _line_n, _line in enumerate(self.read_lines()):

            # Apply check line len
            if _check_line_len:
                _line = _line.split('  # pylint:', 1)[0]
                if len(_line) > 80:
                    raise error.FileError(
                        'Line too long', file_=self, line_n=_line_n + 1)

    @get_method_to_file_cacher(mtime_outdates=True)
    def has_passed_checks(self, val=False, force=False):
        """Check whether this file has already been checked.

        Args:
            val (bool): checked status to apply
            force (bool): force write status to disk

        Returns:
            (bool): whether file has been checked
        """
        return val

    def is_test(self):
        """Check whether this file is a unit/integration test.

        Returns:
            (bool): whether this is a test file
        """
        return '/tests/' in self.path

    def _batch_apply_pylint_unused_imports(self, write=True, force=False):
        """Batch apply pylint unused import issues.

        Args:
            write (bool): apply updates (disable for testings)
            force (bool): apply updates without confirmation

        Returns:
            (str): updated code
        """
        _issues = self.find_pylint_issues(code='W0611')
        _cur = self.read()
        if len(_issues) < 2:
            return _cur
        _fixed = r_issue.fix_unused_imports(file_=self, issues=_issues)
        if write and _fixed != _cur:
            self.write(
                _fixed, diff=True, wording='Batch apply unused imports?',
                force=force)
        return _fixed

    @get_method_to_file_cacher(mtime_outdates=True)
    def to_pycodestyle_reading(self, ignore=(), force=False):
        """Obtain pycodestyle reading for this file.

        Args:
            ignore (list): list of issues to ignore
            force (bool): force regenerate checks data

        Returns:
            (str): pycodestyle reading
        """
        _exe = find_exe('pycodestyle')
        _ignore = list(ignore) + [
            'E402',  # module level import not at top of file (use pylint)
            'E501',  # line too long
            'W504',  # line break after binary operator'
        ]
        _cmds = [
            _exe,
            self,
            '--format', 'pylint',
        ]
        if _ignore:
            _cmds += ['--ignore', ','.join(_ignore), '--verbose']
        _result = system(_cmds, verbose=1)
        assert f'checking {self.path}' in _result
        return _result

    def find_pylint_issues(self, filter_=None, code=None, force=False):
        """Find pylint issues in this file.

        Args:
            filter_ (str): apply issue filter
            code (str): apply code filter
            force (bool): force reread issues from disk

        Returns:
            (PylintIssue list): matching issues
        """
        _reading = self.to_pylint_reading(force=force)
        _issues = []
        for _issue in r_issue.to_pylint_issues(_reading):
            if code and _issue.code != code:
                continue
            if filter_ and not passes_filter(_issue.filter_str, filter_):
                continue
            _issues.append(_issue)
        return _issues

    @get_method_to_file_cacher(mtime_outdates=True)
    def to_pylint_reading(self, force=False):
        """Obtain pylint reading for this file.

        Args:
            force (bool): force regenerate checks data

        Returns:
            (str): pylint reading
        """
        from pini.tools import release

        # Find checks to disable
        _disable = set()
        if self.is_test():
            _disable |= {
                'C2801',  # unnecessary-dunder-call
                'C0301',  # line-too-long
                'R0915',  # too-many-statements
                'W0212',  # protected-access
                'W0613',  # unused-argument
            }
        for _check, _filter in _obt_cfg()['disable_checks'].items():
            if passes_filter(self.path, _filter):
                _disable.add(_check)
        _disable = sorted(_disable)
        _LOGGER.info(' - DISABLE CHECKS %s', _disable)

        # Add dev code to init hook
        _py_dirs = []
        for _repo in release.REPOS:
            _py = _repo.to_subdir('python')
            if _py.exists():
                _py_dirs.append(_py)
        _init = []
        if _py_dirs:
            _init += ['import sys']
            for _py_dir in _py_dirs:
                _init.append(f"sys.path.insert(0, '{_py.path}')")

        # Build lint cmd
        _pylint = find_exe('pylint')
        _cmds = [
            _pylint,
            self,
            '-f', 'parseable',
            '--extension-pkg-whitelist=PySide',
            '--rcfile', _PYLINT_RC,
        ]
        if _disable:
            _cmds += ['--disable', ','.join(_disable)]
        if _init:
            _init_py = '; '.join(_init)
            _cmds += ['--init-hook', _init_py]

        _out, _err = system(_cmds, result='out/err', verbose=1)
        if 'Your code has been rated at' not in _out:
            _LOGGER.info('OUT')
            print(_out)
            _LOGGER.info('ERR')
            print(_err)
            raise RuntimeError(f'Linting failed {self.path}')
        return _out


def check_file(file_, pylint=True, pycodestyle=True):
    """Apply release checks to the given file.

    Args:
        file_ (str): path to file to check
        pylint (bool): apply pylint checks
        pycodestyle (bool): apply pycodestyle checks
    """
    _path = abs_path(to_str(file_))
    _file = CheckFile(_path)
    _file.apply_checks(pylint=pylint, pycodestyle=pycodestyle)


@cache_result
def _obt_cfg(force=False):
    """Obtain release config.

    Args:
        force (bool): force reread from disk

    Returns:
        (dict): release config
    """
    _LOGGER.info('READING RELEASE CONFIG')
    _cfg = {'disable_checks': {}}

    _cfg_file = os.environ.get('PINI_RELEASE_CFG')
    _LOGGER.info(' - CFG FILE %s', _cfg_file)
    if _cfg_file:
        _file_cfg = File(_cfg_file).read_yml() or {}
        _LOGGER.info(' - FILE CFG %s', _file_cfg)
        _cfg = merge_dicts(_cfg, _file_cfg)
    return _cfg
