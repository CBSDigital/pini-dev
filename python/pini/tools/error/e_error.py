"""Tools for managing error tracebacks."""

import logging
import platform
import sys
import traceback

from pini import dcc, icons
from pini.tools import usage
from pini.utils import nice_age, email, basic_repr, to_session_dur

from . import e_trace_line

_LOGGER = logging.getLogger(__name__)


class PEError:
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
        _text = f'{prefix}Traceback (most recent call last):\n'
        for _line in self.lines:
            _text += _line.to_text(prefix=prefix + '  ') + '\n'
        _text += f'{prefix}{self.type_name}: {self.message}'
        return _text.strip()

    def send_email(self):
        """Send email to support for this error."""
        from pini import qt
        from .e_dialog import EMOJI

        _dcc_ver = '-' + dcc.to_version(str) if dcc.NAME else ''
        _lines = [
            f'<b>DCC</b> {dcc.NAME}{_dcc_ver}',
            f'<b>SCENE</b> {dcc.cur_file()}',
            f'<b>MACHINE</b> {platform.node()}',
            f'<b>PINI SESSION</b> {nice_age(to_session_dur("pini"))}',
            f'<b>DCC SESSION</b> {nice_age(to_session_dur("dcc"))}',
            '',
        ]
        for _mod, _ver in usage.get_mod_vers():
            _lines += [f'<b>{_mod.upper()}</b> v{_ver.string}']
        _exc = self.to_text(prefix='# ').replace('\n', '<br>\n')
        _lines += [
            '',
            '<b>EXCEPTION</b>',
            '',
            f'<code><font size="4">{_exc}</font></code>',
        ]
        _body = '<br>\n'.join(_lines)
        _body = _body.replace(' ', '&nbsp;')

        _icon = EMOJI.to_unicode()
        _subject = _icon + f' [ERROR] {self.message}'

        email.send_email(
            email.SUPPORT_EMAIL, subject=_subject, body=_body, html=True,
            cc_=email.FROM_EMAIL)
        qt.notify(
            f'Sent error email to:\n\n{email.SUPPORT_EMAIL.lower()}',
            icon=icons.find('Lemon'), title='Email sent')

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

    # Extract (last) traceback lines
    _tb = traceback_.strip()
    _tb = _tb.split(
        'During handling of the above exception, another exception '
        'occurred:')[-1]
    _tb = _tb.split(
        'The above exception was the direct cause of the following '
        'exception:')[-1]
    _tb_lines = _tb.strip().split('\n')
    _tb_lines = [_line for _line in _tb_lines if _line.strip(' ^')]

    # Flag bad traceback
    if (
            _tb_lines[0] != 'Traceback (most recent call last):' or
            len(_tb_lines) % 2):
        _LOGGER.info(' - TOP LINE "%s"', _tb_lines[0])
        _LOGGER.info(' - LINE COUNT "%s"', len(_tb_lines))
        _LOGGER.info(' - LINES %s', _tb_lines)
        print('----------------------------------------------------')
        print('----------- INVALID TRACEBACK (START) --------------')
        print('----------------------------------------------------')
        print(_tb)
        print('----------------------------------------------------')
        print('------------ INVALID TRACEBACK (END) ---------------')
        print('----------------------------------------------------')
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
        _e_line = e_trace_line.line_from_str(_tb_top + '\n' + _tb_bot)
        _e_lines.append(_e_line)

    return PEError(type_name=_type_name, message=_msg, lines=_e_lines)
