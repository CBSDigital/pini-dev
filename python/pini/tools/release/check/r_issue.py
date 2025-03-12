"""Tools for managing pylint and pycodestyle issues."""

import logging
import operator
import re
import textwrap

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


def fix_unused_imports(file_, issues):
    """Apply batch unused imports fix.

    Batch apply multiple unused imports issues on the given file.

    Args:
        file_ (str): path to file to update
        issues (PylintIssue list): unused import errors

    Returns:
        (str): updated code
    """
    assert len(issues) >= 2
    # _issues = r_issue.to_pycodestyle_issues(_reading)
    _LOGGER.debug('FOUND %d pylint ISSUES', len(issues))

    issues.sort(key=operator.attrgetter('line_n'), reverse=True)
    _lines = file_.read_lines()
    # pprint.pprint(_lines)

    for _issue in issues:

        # Compact statement lines into single line
        _line_n = _issue.line_n - 1
        _LOGGER.info(
            ' - FIX ISSUE %s %d %s', _issue, _issue.line_n, _issue.desc)
        _line = _lines[_line_n]
        if _line.endswith('('):  # Compact nested lines into one
            _line = _line.rstrip(' (')
            _next_n = _line_n + 1
            for _ in range(20):
                _LOGGER.info(' - CHECKING NEXT LINE %s', _next_n)
                if _next_n >= len(_lines):
                    _LOGGER.info(' - OVERFLOW')
                    break
                _LOGGER.info('   - NEXT LINE %s', _lines[_next_n])
                _line += ' ' + _lines.pop(_next_n).strip(' )')
                # _lines[_next_n]
                _LOGGER.info('     -> LINE %s', _line)
                if (
                        not _lines[_next_n].strip() or
                        _lines[_next_n][0] != ' '):
                    break
        _LOGGER.info('   - LINE %s', _line)

        # Simple one line imports (eg. "import sys")
        if _issue.desc.startswith('Unused import '):

            assert _issue.desc.count('Unused import ') == 1
            _token = _issue.desc.replace('Unused import ', '')
            _LOGGER.info('   - TOKEN %s', _token)
            if _line == f'import {_token}':
                _lines.pop(_line_n)
            elif _line.endswith(f' import {_token}'):
                _lines.pop(_line_n)
            else:
                raise NotImplementedError

        # Batch from imports (eg. "from pini import pipe, install")
        elif ' imported from ' in _issue.desc:

            _fix_unused_from_import(
                lines=_lines, issue=_issue, line=_line)

        elif _issue.desc.endswith(' imported from'):
            assert _issue.desc.startswith('Unused ')
            assert _issue.desc.count(' imported from') == 1
            assert _issue.desc.count('Unused ') == 1
            _token = _issue.desc.replace(
                'Unused ', '').replace(' imported from', '')
            assert _line.strip().startswith('from ')
            assert _line.endswith(f' import {_token}')
            _lines.pop(_line_n)

        else:
            raise NotImplementedError(f'Unhandled "{_issue.desc}"')

    return '\n'.join(_lines)


def _fix_unused_from_import(issue, lines, line):
    """Fix unused "from" style import.

    eg. from pini import pipe, install

    Args:
        issue (PylintIssue): unused import issue
        lines (str list): lines of code being fixed
        line (str): issue's line of code (cleaned)
    """
    assert issue.desc.startswith('Unused ')
    _line_n = issue.line_n - 1

    _tail = issue.desc[len('Unused '):]
    if ' as ' in issue.desc:  # eg. from xxx import yyy as zzz
        _submod, _tail = _tail.split(' imported from ')
        _LOGGER.info('   - SUBMOD %s', _submod)
        _root, _alias = _tail.split(' as ')
        _LOGGER.info('   - ALIAS %s', _alias)
        _to_remove = f'{_submod} as {_alias}'
    else:
        _to_remove, _root = _tail.split(' imported from ')
    _LOGGER.info('   - ROOT %s', _root)
    _LOGGER.info('   - TO REMOVE %s', _to_remove)
    assert line.count(_to_remove) == 1

    # Handle single from import
    _match_full_line = f'from {_root} import {_to_remove}'
    _LOGGER.info('   - MATCH FULL LINE %s', _match_full_line)
    if line.strip() == _match_full_line:
        lines.pop(_line_n)
        return

    _prefix = f'from {_root} import '
    _LOGGER.info('   - PREFIX %s', _prefix)
    assert line.strip().startswith(_prefix)
    assert line.count(_prefix) == 1
    _imports = line[len(_prefix):].split(', ')
    _LOGGER.info('   - IMPORTS %s', _imports)

    # Build new line(s)
    _new_line = line.replace(_to_remove, '')
    _new_line = _new_line.replace(', , ', ', ')
    if _new_line.endswith(', '):
        _new_line = _new_line[:-2]
    _new_line = _new_line.replace(' , ', ' ')
    _LOGGER.info('   - NEW LINE %s', _new_line)
    if len(line) <= 80:
        lines[_line_n] = _new_line
    else:
        _LOGGER.info('   - SPLITTING LONG LINE')
        _prefix = f'from {_root} import '
        assert _new_line.startswith(_prefix)
        lines[_line_n] = _prefix + '('
        _mod_list = _new_line[len(_prefix):] + ')'
        _LOGGER.info('   - MOD LIST %s', _mod_list)
        _mod_lines = textwrap.wrap(
            _mod_list, width=76, initial_indent='    ',
            subsequent_indent='    ')
        for _line in reversed(_mod_lines):
            lines.insert(_line_n + 1, _line)


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
        _LOGGER.debug(' - ISSUE %s', _issue)
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
