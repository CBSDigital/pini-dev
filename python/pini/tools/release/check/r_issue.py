"""Tools for managing pylint and pycodestyle issues."""

import logging
import re

# from pini.tools import error
from pini.utils import basic_repr

_LOGGER = logging.getLogger(__name__)


class _Issue:
    """Base class for any pylint/pycodestype issue."""

    def __init__(self, code, desc, line_n):
        """Constructor.

        Args:
            code (str): lint code (eg. E0401)
            desc (str): issue description (eg. "Unable to import 'nuke'")
            line_n (int): issue line number
        """
        self.code = code
        self.desc = desc
        self.line_n = line_n

    def to_error(self, file_):
        """Build this issue into an error.

        Args:
            file_ (PyFile): file triggering issue

        Returns:
            (FileError): error for this issue
        """
        from pini.tools import error
        return error.FileError(self.desc, file_=file_, line_n=self.line_n)

    def __repr__(self):
        return basic_repr(self, f'{self.code}')


class _PycodestyleIssue(_Issue):
    """Represents a pycodestyle issue.

    ie. a line in a pycodestyle result.

    eg.
    aw_callbacks.py:68:23: W504 line break after binary operator
    """

    def __init__(self, line):
        """Constructor.

        Args:
            line (str): issue text
        """
        _LOGGER.debug('INIT PycodestyleIssue %s', line)
        self.line = line
        _head, _tail = line.split(': ', 1)
        _line_n = int(_head.rsplit(':')[-1])
        _LOGGER.debug(' - TAIL %s', _tail)
        _, _code, _desc = re.split(r'[\[\]]', _tail)
        super().__init__(desc=_desc.strip(), code=_code, line_n=_line_n)


class _PylintIssue(_Issue):
    """Represents a pylint issue.

    ie. a line in a pylint result.

    eg.
    test.py:15:4: R0915: Too many statements (55/50) (too-many-statements)
    """

    def __init__(self, line):
        """Constructor.

        Args:
            line (str): issue text
        """
        self.line = line
        _head, _tail = line.split(': ', 1)
        _line_n = int(_head.rsplit(':')[-1])
        _, _code_s, _desc = re.split(r'[\[\]]', _tail)
        _code, self.name, _ = re.split('[()]', _code_s)
        super().__init__(desc=_desc.strip(), code=_code, line_n=_line_n)


def to_pycodestyle_issues(reading):
    """Build the give pycodestyle reading into issues.

    Args:
        reading (str): pycodestyle reading

    Returns:
        (PycodestyleIssues list): issues
    """
    _issues = []
    for _line in reading.split('\n'):
        _LOGGER.debug('CHECK LINE %s', _line)
        try:
            _issue = _PycodestyleIssue(_line)
        except ValueError:
            continue
        _LOGGER.info(' - ISSUE %s', _issue)
        _issues.append(_issue)
    return _issues


def to_pylint_issues(reading):
    """Build the give pylint reading into issues.

    Args:
        reading (str): pylint reading

    Returns:
        (PylintIssues list): issues
    """
    _issues = []
    for _line in reading.split('\n'):
        _LOGGER.debug('CHECK LINE %s', _line)
        try:
            _issue = _PylintIssue(_line)
        except ValueError:
            continue
        _LOGGER.info(' - ISSUE %s', _issue)
        _issues.append(_issue)
    return _issues
