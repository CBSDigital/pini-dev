"""Tools for handling reading urls."""

import logging
import time
import urllib
import urllib.error
import urllib.request


_LOGGER = logging.getLogger(__name__)


class _UrlNotFound(RuntimeError):
    """Raised when the url is not found."""


class _UrlReadError(Exception):
    """Raised when the url reader fails."""


def _execute_url_read(url):
    """Execute a url read.

    Args:
        url (str): url to read

    Returns:
        (dict): url data
    """
    _LOGGER.debug('READ URL %s', url)

    # Obtain response
    try:
        _response = urllib.request.urlopen(url)
    except urllib.error.HTTPError as _exc:
        _LOGGER.info(' - EXC "%s"', _exc)
        if str(_exc) == 'HTTP Error 404: Not Found':
            raise _UrlNotFound(f'Not found {url}') from _exc
        raise _exc

    # Decode response
    _data = ''
    for _line in _response:
        _data += _line.decode('utf-8')

    return _data


def read_url(url, edit=False, attempts=5):
    """Read url contents.

    Args:
        url (str): url to read
        edit (bool): save html and open in editor
        attempts (int): number of attempts to download url

    Returns:
        (str): url response
    """
    from pini.utils import TMP

    # Attempt to read data
    _data = _response = None
    for _idx in range(attempts):
        try:
            _data = _execute_url_read(url)
        except _UrlReadError as _exc:
            _LOGGER.info(
                'FAILED(%s) - %d %s',
                type(_exc).__name__, _idx + 1, str(_exc))
            time.sleep(2)
        else:
            break

    if not _data:
        raise RuntimeError('Failed to read ' + url)
    assert isinstance(_data, str)

    if edit:
        _tmp_html = TMP.to_file('tmp.html')
        _tmp_html.write(_data, force=True, encoding='utf-8')
        _tmp_html.edit()
        _LOGGER.info('Saved tmp html %s', _tmp_html)

    return _data
