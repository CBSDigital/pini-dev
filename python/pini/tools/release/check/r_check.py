"""Tools for managing the check file object."""

import logging

from pini.tools import error
from pini.utils import (
    File, PyFile, find_exe, system, cache_method_to_file,
    MetadataFile, TMP, PyDef, PyClass, strftime)

from . import r_docs, r_issue

DIR = File(__file__).to_dir()

_LOGGER = logging.getLogger(__name__)
_PYLINT_RC = DIR.to_file('pylint.rc')


class CheckFile(MetadataFile):
    """Represents a file being released."""

    cache_loc = 'home'
    cache_namespace = 'release'

    def apply_checks(self, force=False):
        """Apply release checks.

        Args:
            force (bool): force regenerate checks data
        """
        self.apply_docs_check()
        self.apply_autofix()
        self.apply_simple_checks()
        self.apply_pylint_check(force=force)
        self.apply_pycodestyle_check(force=force)

    def apply_autofix(self, diff=False, force=False):
        """Apply autofixes.

        Args:
            diff (bool): show diffs before update
            force (bool): apply updates without confirmation
        """

        _orig = self.read()

        # Check code line by line
        _lines = []
        for _line in _orig.strip().split('\n'):

            _line = _line.rstrip()
            _tokens = _line.split()

            # Enforce double newline above def/class
            if (
                    _tokens and
                    _tokens[0] in ('def', 'class')):
                _lines += ['', '']
                _LOGGER.info(' - ADDED NEWLINES %s', _lines)
                while len(_lines) > 2 and _lines[-3] == '':
                    _lines.pop(-3)
                    _LOGGER.info(' - CROPPED NEWLINES %s', _lines)

            _lines.append(_line)

        # Save updated code
        _fixed = '\n'.join(_lines) + '\n'
        if _orig != _fixed:
            _LOGGER.info('AUTOFIXES WERE FOUND')
            if diff:
                raise NotImplementedError
            assert self.dir[1] == ':'
            assert self.dir[2] == '/'
            _t_stamp = strftime()
            _bkp = TMP.to_file(
                f'.pini/release/autofix/{self.dir[3:]}/'
                f'{self.base}_{_t_stamp}.{self.extn}')
            _LOGGER.info(' - BKP %s', _bkp.path)
            self.copy_to(_bkp, force=True)
            _LOGGER.info(' - UPDATING %s', self.path)
            self.write(_fixed, force=force)

    def apply_docs_check(self):
        """Apply docstrings checks."""
        _is_test = '/tests/' in self.path
        if _is_test:
            return
        if self.filename == '__init__.py' and not self.read():
            return

        _py = PyFile(self)

        r_docs.check_mod_docs(_py)

        for _item in _py.find_children():
            if isinstance(_item, PyDef):
                r_docs.check_def_docs(_item)
            elif isinstance(_item, PyClass):
                r_docs.check_class_docs(_item)
            else:
                raise ValueError(_item)

    def apply_pycodestyle_check(self, force=False):
        """Apply pycodestyle checks.

        Args:
            force (bool): force regenerate checks data
        """
        _reading = self.to_pycodestyle_reading(force=force)
        _issues = r_issue.to_pycodestyle_issues(_reading)
        _LOGGER.info('FOUND %d pycodestyle ISSUES', len(_issues))
        for _issue in _issues:
            _LOGGER.info(' - ISSUE %s %s', _issue, _issue.desc)
            raise _issue.to_error(self)
        _LOGGER.info(' - PYCODESTYLE SUCCESFUL %s', self.path)

    def apply_pylint_check(self, force=False):
        """Apply pylint checks.

        Args:
            force (bool): force regenerate checks data
        """
        _reading = self.to_pylint_reading(force=force)
        _issues = r_issue.to_pylint_issues(_reading)
        _LOGGER.info('FOUND %d pylint ISSUES', len(_issues))
        for _issue in _issues:
            _LOGGER.info(' - ISSUE %s %s %s', _issue, _issue.name, _issue.desc)
            _LOGGER.info(' - DISABLE # pylint: disable=%s', _issue.name)
            raise _issue.to_error(self)
        _LOGGER.info(' - LINT SUCCESFUL %s', self.path)

    def apply_simple_checks(self):
        """Apply simple checks."""
        for _line_n, _line in enumerate(self.read_lines()):
            _line = _line.split('  # pylint:', 1)[0]
            if len(_line) > 80:
                raise error.FileError(
                    'Line too long', file_=self, line_n=_line_n)

    def is_test(self):
        """Check whether this file is a unit/integration test.

        Returns:
            (bool): whether this is a test file
        """
        return '/tests/' in self.path

    @cache_method_to_file
    def to_pycodestyle_reading(self, force=False):
        """Obtain pycodestyle reading for this file.

        Args:
            force (bool): force regenerate checks data

        Returns:
            (str): pycodestyle reading
        """
        _exe = find_exe('pycodestyle')
        _ignore = [
            'E501',  # line too long
            'W504',  # line break after binary operator
        ]
        _cmds = [
            _exe,
            self,
            '--format', 'pylint',
        ]
        if _ignore:
            _cmds += ['--ignore', ','.join(_ignore)]
        return system(_cmds)

    @cache_method_to_file
    def to_pylint_reading(self, force=False):
        """Obtain pylint reading for this file.

        Args:
            force (bool): force regenerate checks data

        Returns:
            (str): pylint reading
        """
        _pylint = find_exe('pylint')
        _disable = []
        if self.is_test():
            _disable += [
                'missing-module-docstring',
                'protected-access',
                'too-many-statements',
            ]

        _cmds = [
            _pylint,
            self,
            '-f', 'parseable',
            '--extension-pkg-whitelist=PySide',
            '--rcfile', _PYLINT_RC,
        ]
        if _disable:
            _cmds += ['--disable', ','.join(_disable)]
        return system(_cmds, verbose=1)
