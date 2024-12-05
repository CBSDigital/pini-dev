"""Tools for managing the check heart loop breaker tool."""

import logging
import os
import time

from .path import File, abs_path

HEART = File(os.environ.get('PINI_HEART', abs_path('~/.heart')))

_LOGGER = logging.getLogger(__name__)
_INITIATED = {}
_LAST_CHECK = {}


def check_heart(heart=None):
    """Check heart file exists.

    This is used to break slow/infinite loops without killing the dcc.

    Args:
        heart (str): override heart file
    """

    # Get heart
    if heart:
        _heart = File(abs_path(heart))
    else:
        _heart = HEART
    _LOGGER.log(9, 'CHECK HEART %s', _heart.path)

    if os.environ.get('PINI_DISABLE_FILE_SYSTEM'):
        _LOGGER.log(9, ' - FILE SYSTEM DISABLED - IGNORING')
        return

    # Make sure heart exists
    if not _INITIATED.get(_heart, False):
        _LOGGER.log(9, ' - INITIATING')
        _heart.touch()
        _INITIATED[_heart] = True

    # Only check once a second
    if (
            _LAST_CHECK.get(_heart) and
            time.time() - _LAST_CHECK[_heart] < 1.0):
        _LOGGER.log(9, ' - CHECKED RECENTLY - IGNORING')
        return

    if not _heart.exists():
        _heart.touch()
        raise RuntimeError(f"Missing heart {_heart.path}")

    _LAST_CHECK[_heart] = time.time()
    _LOGGER.log(9, ' - CHECKED')
