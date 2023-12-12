"""Tools for managing release notes."""

import logging

from pini.utils import strftime, basic_repr

_LOGGER = logging.getLogger(__name__)


class PRNotes(object):
    """Represents release notes.

    These consist of a summary and a more detail tech notes.
    """

    def __init__(self, summary, tech_notes):
        """Constructor.

        Args:
            summary (str): summary of changes
            tech_notes (str): module by module technical breakdown
                of changes
        """
        assert summary and tech_notes
        assert summary != tech_notes
        self.summary = summary.strip().strip(',')
        self.tech_notes = tech_notes.strip().strip(',')

        for _notes, _start_upper in [
                (self.summary, True),
                (self.tech_notes, False)]:

            assert _notes

            _lines = _notes.split('\n')
            for _line in _lines:

                _LOGGER.debug(' - CHECKING LINE %s', _line)

                _line = _line.strip(',')
                _line = _line.rstrip()

                # Check head
                if (
                        not (_line[0].isalpha() or _line[0] in '.') and
                        not _line.startswith(' - ')):
                    raise ValueError(_line)
                if (
                        _start_upper and
                        _line[0].isalpha() and
                        not _line.strip(' -')[0].isupper()):
                    raise ValueError('Head fail - '+_line)

                # Check tail
                if (
                        not _line[-1].isalpha() and
                        not _line[-1].isdigit() and
                        not _line[-1] in '):_]'):
                    raise ValueError(_line)
                assert '"' not in _line

        self._summary_lines = [
            _line.strip(',').rstrip()
            for _line in self.summary.split('\n')]
        self._tech_lines = [
            _line.strip(',').rstrip()
            for _line in self.tech_notes.split('\n')]

    def get_users(self):
        """Get users mentioned in notes.

        Returns:
            (str set): set of users
        """
        _users = set()
        for _line in self._summary_lines:
            if '(' not in _line:
                continue
            _users |= set(str(_line).split('(')[-1].split(')')[0].split('/'))
        for _user in _users:
            assert _user.islower()
            assert _user.isalpha()
        return _users

    def to_changelog(self, ver, mtime):
        """Express these notes in CHANGELOG format.

        Args:
            ver (PRVersion): version being released
            mtime (float): release time

        Returns:
            (str): notes in CHANGELOG format
        """
        _lines = [
            strftime('## [{}] - %a %Y-%m-%d %H:%M'.format(
                ver.string), mtime),
            '### Summary']
        for _line in self._summary_lines:
            if _line.startswith(' - '):
                _lines += ['   {},'.format(_line)]
            elif _line.endswith(':'):
                _lines += [' - {}'.format(_line)]
            else:
                _lines += [' - {},'.format(_line)]
        _lines.append('### Updated')
        for _line in self._tech_lines:
            _lines.append(' - {},'.format(_line))
        return '\n'.join(_lines)

    def to_cmdline(self, repo, ver):
        """Express these notes in a command line format for git commit.

        Args:
            repo (PRRepo): repo being released
            ver (PRVersion): version being released

        Returns:
            (str): notes in command line format
        """
        return '{}:{} - {} | {}'.format(
            repo.name, ver.string,
            _to_cmdline(self._summary_lines),
            _to_cmdline(self._tech_lines))

    def to_email(self, repo, ver, mtime, diffs_link=None, get_ticket_url=None):
        """To get email body version of these notes.

        Args:
            repo (PRRepo): repo being released
            ver (PRVersion): release version
            mtime (float): release time
            diffs_link (str): view diffs url
            get_ticket_url (fn): function to retrieve ticket urls

        Returns:
            (str): email body
        """
        _vers = repo.find_versions()
        _prev = _vers[-2]
        assert ver == _vers[-1]

        _lines = [
            '<b>Repo</b>: {}'.format(repo.name),
            '<b>Update</b>: {} -> {}'.format(_prev.string, ver.string),
            '<b>Date</b>: '+strftime('%a %b %m - %H:%M %p PST', mtime),
        ]

        # Add notes
        _lines += ['', '<b>Summary:</b>']
        for _line in self._summary_lines:
            _line = _link_tickets(_line, get_ticket_url=get_ticket_url)
            if _line.startswith(' - '):
                _lines += ['   {},'.format(_line)]
            elif _line.strip().endswith(':'):
                _lines += [' - {}'.format(_line)]
            else:
                _lines += [' - {},'.format(_line)]
        _lines += ['', '<b>Tech notes:</b>']
        for _line in self._tech_lines:
            _lines += [' - {},'.format(_line)]

        # Add show diffs
        _diffs = '<a href={}>View diffs</a>'.format(diffs_link)
        _lines += ['', _diffs]

        _body = '\n'.join(_lines)
        _body = _body.replace('\n', '<br>\n')
        _body = _body.replace('    ', '&emsp;&emsp;')
        return _body

    def __repr__(self):
        return basic_repr(self, label=None)


def _to_cmdline(lines):
    """Convert the given lines to command line format.

    Args:
        lines (str line): lines of notes

    Returns:
        (str): formatted lines
    """
    _lines = ''
    for _line in lines:
        _line = _line.strip(' -').replace("'", "\\'")
        _lines += _line
        if not _line.endswith(':'):
            _lines += ','
        _lines += ' '
    return _lines.rstrip(', ')


def _link_tickets(line, get_ticket_url):
    """Apply links to any ticket references in the given line.

    eg. "Updated something [TRELLO-12]" should link to that
    ticket.

    Args:
        line (str): line of release summary to update
        get_ticket_url (fn): function to provide ticket url

    Returns:
        (str): updated line
    """
    _line = line
    if '[' not in line and ']' not in line:
        return line
    for _chunk in line.split('[')[1:]:
        _ticket = _chunk.split(']')[0]
        _ticket_str = '[{}]'.format(_ticket)
        _url = get_ticket_url(_ticket)
        _link = '<a href={}>{}</a>'.format(_url, _ticket_str)
        _line = _line.replace(_ticket_str, _link)
    return _line
