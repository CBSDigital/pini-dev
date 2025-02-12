"""Tools for managing the check file object."""

import logging

from pini.utils import (
    File, PyFile, find_exe, system, get_method_to_file_cacher,
    MetadataFile, PyDef, PyClass, abs_path, to_str)

from . import r_docs, r_issue, r_autofix

DIR = File(__file__).to_dir()

_LOGGER = logging.getLogger(__name__)
_PYLINT_RC = DIR.to_file('pylint.rc')


class CheckFile(MetadataFile):
    """Represents a file being released."""

    cache_loc = 'home'
    cache_namespace = 'release'

    def apply_checks(
            self, pylint=True, pycodestyle=True, pylint_disable=(),
            force=False):
        """Apply release checks.

        Args:
            pylint (bool): apply pylint checks
            pycodestyle (bool): apply pycodestyle checks
            pylint_disable (list): list of pylint issues to ignore
            force (bool): force regenerate checks data
        """
        if self.has_passed_checks():
            return

        # Run checks
        self.apply_docs_check()
        self.apply_autofix()
        self.apply_simple_checks()
        if pylint:
            self.apply_pylint_check(force=force, disable=pylint_disable)
        if pycodestyle:
            self.apply_pycodestyle_check(force=force, ignore=pylint_disable)

        # Mark as checked
        self.has_passed_checks(True, force=True)

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

        _py = PyFile(self)

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

    def apply_pycodestyle_check(self, ignore=(), force=False):
        """Apply pycodestyle checks.

        Args:
            ignore (list): list of issues to ignore
            force (bool): force regenerate checks data
        """
        _reading = self.to_pycodestyle_reading(ignore=ignore, force=force)
        _issues = r_issue.to_pycodestyle_issues(_reading)
        _LOGGER.debug('FOUND %d pycodestyle ISSUES', len(_issues))
        for _issue in _issues:
            _LOGGER.debug(' - ISSUE %s %s', _issue, _issue.desc)
            raise _issue.to_error(self)
        _LOGGER.debug(' - PYCODESTYLE SUCCESFUL %s', self.path)

    def apply_pylint_check(self, disable=(), force=False):
        """Apply pylint checks.

        Args:
            disable (list): list of issues to ignore
            force (bool): force regenerate checks data
        """
        _reading = self.to_pylint_reading(disable=disable, force=force)
        _issues = r_issue.to_pylint_issues(_reading)
        _LOGGER.debug('FOUND %d pylint ISSUES', len(_issues))
        for _issue in _issues:
            _LOGGER.info(' - ISSUE %s %s %s', _issue, _issue.name, _issue.desc)
            _LOGGER.info(' - DISABLE # pylint: disable=%s', _issue.name)
            raise _issue.to_error(self)
        _LOGGER.debug(' - LINT SUCCESFUL %s', self.path)

    def apply_simple_checks(self):
        """Apply simple checks."""
        from pini.tools import error

        for _line_n, _line in enumerate(self.read_lines()):

            # Check for line too long
            if not self.is_test():
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

    @get_method_to_file_cacher(mtime_outdates=True)
    def to_pylint_reading(self, disable=(), force=False):
        """Obtain pylint reading for this file.

        Args:
            disable (list): list of issues to ignore
            force (bool): force regenerate checks data

        Returns:
            (str): pylint reading
        """
        _pylint = find_exe('pylint')
        _disable = list(disable)
        if self.is_test():
            _disable += [
                'line-too-long',
                'missing-module-docstring',
                'protected-access',
                'too-many-statements',
                'unused-argument',
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


def check_file(file_, pylint=True, pycodestyle=True, pylint_disable=()):
    """Apply release checks to the given file.

    Args:
        file_ (str): path to file to check
        pylint (bool): apply pylint checks
        pycodestyle (bool): apply pycodestyle checks
        pylint_disable (tuple): issues to ignore
    """
    _path = abs_path(to_str(file_))
    _file = CheckFile(_path)
    _LOGGER.debug(' - PYLINT DISABLE %s', pylint_disable)
    _file.apply_checks(
        pylint=pylint, pycodestyle=pycodestyle, pylint_disable=pylint_disable)
