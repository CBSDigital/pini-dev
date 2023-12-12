"""Tools for managing error tracebacks."""

import logging
import platform
import sys
import traceback

from pini import dcc, icons
from pini.tools import usage
from pini.utils import nice_age, email, basic_repr

from . import ce_trace_line

_LOGGER = logging.getLogger(__name__)


class CEError(object):
    """Represents an error traceback."""

    def __init__(self):
        """Constructor."""
        self.type_, self.value, self.traceback = sys.exc_info()
        self.lines = []
        for _file, _line_n, _func, _code in traceback.extract_tb(
                self.traceback):
            _line = ce_trace_line.CETraceLine(
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
        _text += '{}{}: {}'.format(prefix, self.type_.__name__, self.value)
        return _text.strip()

    def send_email(self):
        """Send email to support for this error."""
        from pini import qt
        from .ce_dialog import EMOJI
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
        _subject = _icon + ' [ERROR] {}'.format(self.value)

        email.send_email(
            email.SUPPORT_EMAIL, subject=_subject, body=_body, html=True)
        qt.notify('Sent error email to {}'.format(email.SUPPORT_EMAIL),
                  icon=icons.find('Lemon'), title='Email Sent')

    def __repr__(self):
        return basic_repr(self, str(self.value).strip())
