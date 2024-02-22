"""General error handling tools."""

import functools
import logging
import os

_LOGGER = logging.getLogger(__name__)


class HandledError(RuntimeError):
    """Error which requires user to address.

    This is used to supress the error dialog in the case of an error
    which has been anticipated in the code and doesn't need to be sent
    to the developer.
    """

    def __init__(self, message, title=None):
        """Constructor.

        Args:
            message (str): error/dialog message
            title (str): title for error dialog
        """
        super(HandledError, self).__init__(message)
        self.title = title


class FileError(RuntimeError):
    """Raises when a file causes an issue."""

    def __init__(self, message, file_, line_n=None):
        """Constructor.

        Args:
            message (str): error message
            file_ (str): path to file
            line_n (int): line of file causing issue
        """
        super(FileError, self).__init__(message)
        self.file_ = file_
        self.line_n = line_n


def continue_on_fail(func):
    """Ignore any error on function execution and continue.

    Args:
        func (fn): function to execute

    Returns:
        (fn): decorated function
    """

    @functools.wraps(func)
    def _ignore_fail(*args, **kwargs):

        if os.environ.get('PINI_DISABLE_ERROR_SUPRESSION'):
            return func(*args, **kwargs)

        try:
            return func(*args, **kwargs)
        except Exception as _exc:  # pylint: disable=broad-except #
            _LOGGER.info('EXECUTE %s FAILED: %s', func.__name__, _exc)
            return None

    return _ignore_fail
