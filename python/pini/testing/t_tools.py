"""General testing tools."""

import logging
import os
import sys

from pini import icons
from pini.utils import check_heart, TMP, Image

_LOGGER = logging.getLogger(__name__)

TEST_YML = TMP.to_file('test.yml')
TEST_DIR = TMP.to_subdir('PiniTesting')


def dev_mode():
    """Check whether pini dev mode is enabled.

    Returns:
        (bool): whether currently in dev mode
    """
    return os.environ.get('PINI_DEV') == '1'


def obt_image(extn='exr'):
    """Obtain a valid tmp image file of the given format for testing.

    Args:
        extn (str): file format

    Returns:
        (File): image file
    """
    _file = TMP.to_file(base='tmp', extn=extn)
    if not _file.exists():

        _src = Image(icons.find('Green Apple'))
        _src.convert(_file)

    assert _file.exists()

    return _file


def set_dev_mode(value):
    """Set dev mode environment variable.

    Args:
        value (bool): value to apply
    """
    if value:
        os.environ['PINI_DEV'] = '1'
    else:
        del os.environ['PINI_DEV']


def setup_logging():
    """Setup logging with a generic handler."""
    _logger = logging.getLogger()
    _logger.setLevel(logging.INFO)

    # Flush existing handlers
    while _logger.handlers:
        check_heart()
        _handler = _logger.handlers[0]
        _LOGGER.debug(' - REMOVE HANDLER %s', _handler)
        _logger.removeHandler(_handler)

    # Create default handler
    _handler = logging.StreamHandler(sys.stdout)
    _formatter = logging.Formatter(
        '- %(name)s: %(message)s')
    _handler.setFormatter(_formatter)
    _logger.addHandler(_handler)
