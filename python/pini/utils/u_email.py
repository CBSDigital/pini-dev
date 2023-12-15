"""Tools for sending emails using an SMPT server."""

import email
import logging
import os
import smtplib

try:
    from email.MIMEMultipart import MIMEMultipart
except ImportError:
    from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formatdate

import six

from .u_misc import lprint

_LOGGER = logging.getLogger(__name__)

FROM_EMAIL = os.environ.get('PINI_FROM_EMAIL')
SUPPORT_EMAIL = os.environ.get('PINI_SUPPORT_EMAIL')
_EMAIL_SERVER = os.environ.get('PINI_EMAIL_SERVER')


def send_email(to_, subject, body, from_=None, cc_=None, html=False,
               server=None, attach=()):
    """Send an email.

    Args:
        to_ (str|list): list of email recipients
        subject (str): email subject
        body (str): email bodu
        from_ (str): override sender
        cc_ (str|list): carbon copy recipients
        html (bool): code email in html format
        server (str): force SMTP server
        attach (File list): files to attach
    """
    from pini.utils import File, SixIterable

    _server = server or _EMAIL_SERVER
    _from = from_ or FROM_EMAIL

    assert _from
    assert _server
    assert isinstance(attach, SixIterable)

    _to = [to_] if isinstance(to_, six.string_types) else to_
    _cc = [cc_] if isinstance(to_, six.string_types) else cc_

    _email = MIMEMultipart('alternative')
    _email['Subject'] = subject
    _email['From'] = _from
    _email['To'] = (", ").join(_to)
    _email["Date"] = formatdate(localtime=True)
    if cc_:
        _email['Cc'] = (", ").join(_cc)

    _text = MIMEText(body, 'html' if html else 'plain')
    _email.attach(_text)

    # Add attachments
    if attach:
        if isinstance(attach, (six.string_types, File)):
            _attach = [attach]
        elif isinstance(attach, SixIterable):
            _attach = attach
        else:
            raise ValueError(attach)
        for _path in _attach:
            _LOGGER.info('ATTACH %s', _path)
            _file = File(_path)
            assert _file.exists()

            _hook = email.mime.base.MIMEBase('application', "octet-stream")
            _hook.set_payload(open(_file.path, 'rb').read())
            email.encoders.encode_base64(_hook)
            _hook.add_header(
                'Content-Disposition', 'attachment;filename={}'.format(
                    _file.filename))
            _email.attach(_hook)

    _server = smtplib.SMTP(_server)
    _server.sendmail(_from, _to, _email.as_string())
    _server.quit()

    lprint('SENT EMAIL', _to)


def set_from_email(email_):
    """Set return address for emails.

    Args:
        email_ (str): email address to apply
    """
    global FROM_EMAIL
    _LOGGER.info('SET FROM EMAIL %s', email_)
    os.environ['PINI_FROM_EMAIL'] = email_
    FROM_EMAIL = email_
