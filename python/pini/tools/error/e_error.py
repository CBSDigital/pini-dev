"""Tools for managing error tracebacks."""

import logging
import platform
import sys
import traceback

from pini import dcc, icons
from pini.tools import usage
from pini.utils import nice_age, email, basic_repr

from . import e_trace_line

_LOGGER = logging.getLogger(__name__)


class PEError(object):
    """Represents an error traceback."""

    def __init__(self, type_name=None, message=None, lines=None):
        """Constructor.

        Args:
            type_name (str): override error type name (eg. 'ValueError')
            message (str): override error message (eg. 'file not found')
            lines (PETraceLine list): override trackback lines
        """
        _type, _msg, _traceback = sys.exc_info()
        self.message = message or _msg

        # Set type name
        self.type_name = None
        if type_name:
            self.type_name = type_name
        elif _type:
            self.type_name = _type.__name__

        # Set lines
        if lines:
            self.lines = lines
        else:
            self.lines = []
            _tb_data = traceback.extract_tb(_traceback)
            for _file, _line_n, _func, _code in _tb_data:
                _line = e_trace_line.PETraceLine(
                    file_=_file, line_n=_line_n, func=_func, code=_code)
                self.lines.append(_line)

    def to_text(self, prefix='# '):
        """Get traceback text for this error.

        Args:
            prefix (str): add prefix

        Returns:
            (str): error text
        """
        _text = '{}Traceback (most recent call last):\n'.format(prefix)
        for _line in self.lines:
            _text += _line.to_text(prefix=prefix+'  ')+'\n'
        _text += '{}{}: {}'.format(prefix, self.type_name, self.message)
        return _text.strip()

    def send_email(self):
        """Send email to support for this error."""
        from pini import qt
        from .e_dialog import EMOJI

        _lines = [
            '<b>DCC</b> {}{}'.format(
                    dcc.NAME,
                    '-'+dcc.to_version(str) if dcc.NAME else ''),
            '<b>SCENE</b> {}'.format(dcc.cur_file()),
            '<b>MACHINE</b> {}'.format(platform.node()),
            '<b>SESSION</b> {}'.format(nice_age(usage.get_session_dur())),
            '',
        ]
        for _mod, _ver in usage.get_mod_vers():
            _lines += ['<b>{}</b> v{}'.format(_mod.upper(), _ver.string)]
        _lines += [
            '',
            '<b>EXCEPTION</b>',
            '',
            '<code><font size="4">{}</font></code>'.format(
                self.to_text(prefix='# ').replace('\n', '<br>\n')),
        ]
        _body = '<br>\n'.join(_lines)
        _body = _body.replace(' ', '&nbsp;')

        _icon = EMOJI.to_unicode()
        _subject = _icon + ' [ERROR] {}'.format(self.message)

        email.send_email(
            email.SUPPORT_EMAIL, subject=_subject, body=_body, html=True,
            cc_=email.FROM_EMAIL)
        qt.notify('Sent error email to {}'.format(email.SUPPORT_EMAIL),
                  icon=icons.find('Lemon'), title='Email Sent')

    def __repr__(self):
        return basic_repr(self, str(self.message).strip())


def error_from_str(traceback_):
    """Build an error object from the given traceback string.

    Args:
        traceback_ (str): full traceback string

    Returns:
        (PEError): error
    """
    _LOGGER.debug('ERROR FROM STR')
    _LOGGER.debug('-------------------------')
    _LOGGER.debug(traceback_)
    _LOGGER.debug('-------------------------')

    _tb_lines = traceback_.strip().split('\n')

    # Flag bad traceback
    if (
            _tb_lines[0] != 'Traceback (most recent call last):' or
            len(_tb_lines) % 2):
        print('-------------------------')
        print(traceback_)
        print('-------------------------')
        raise RuntimeError('Invalid traceback str')

    _tail = _tb_lines.pop(-1)
    if ':' in _tail:
        _type_name, _msg = _tail.split(':', 1)
    else:
        _type_name, _msg = _tail, ''

    _tb_lines.pop(0)

    # Build error lines
    assert not len(_tb_lines) % 2
    _e_lines = []
    while _tb_lines:
        _tb_top = _tb_lines.pop(0)
        _tb_bot = _tb_lines.pop(0)
        _e_line = e_trace_line.line_from_str(_tb_top+'\n'+_tb_bot)
        _e_lines.append(_e_line)

    return PEError(type_name=_type_name, message=_msg, lines=_e_lines)
