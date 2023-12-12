"""General testing tools."""

import logging
import os
import sys

from pini.utils import Dir, TMP_PATH, check_heart

_LOGGER = logging.getLogger(__name__)

TEST_YML = Dir(TMP_PATH).to_file('test.yml')
TEST_DIR = Dir(TMP_PATH).to_subdir('PiniTesting')


def dev_mode():
    """Check whether pini dev mode is enabled.

    Returns:
        (bool): whether currently in dev mode
    """
    return os.environ.get('PINI_DEV') == '1'


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
