"""General error handling tools."""

import functools
import logging
import os

_LOGGER = logging.getLogger(__name__)
_ENV_VARS = {
    "ErrorCatcher": 'PINI_DISABLE_ERROR_CATCHER',
    "FileError": 'PINI_DISABLE_FILE_ERROR',
}


class HandledError(RuntimeError):
    """Error which requires user to address.

    This is used to supress the error dialog in the case of an error
    which has been anticipated in the code and doesn't need to be sent
    to the developer.
    """

    def __init__(self, message, title=None, icon=None):
        """Constructor.

        Args:
            message (str): error/dialog message
            title (str): title for error dialog
            icon (str): path to dialog icon
        """
        from pini import icons
        super().__init__(message)
        self.title = title
        self.icon = icon or icons.find('Hot Pepper')


class FileError(RuntimeError):
    """Raises when a file causes an issue."""

    def __init__(self, message, file_, line_n=None):
        """Constructor.

        Args:
            message (str): error message
            file_ (str): path to file
            line_n (int): line of file causing issue
        """
        super().__init__(message)
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


def is_disabled(mode='ErrorCatcher'):
    """Check whether the error catcher is disabled.

    Args:
        mode (str): aspect to check

    Returns:
        (bool): whether disabled
    """
    _env = _ENV_VARS[mode]
    return os.environ.get(_env) == '1'


def toggle(mode='ErrorCatcher', enabled=None):
    """Toggle error catcher on/off.

    Args:
        mode (str): aspect to toggle
        enabled (bool): state to apply
    """
    _env = _ENV_VARS[mode]
    _enable = is_disabled(mode=mode) if enabled is None else enabled
    if _enable:
        if _env in os.environ:
            del os.environ[_env]
        _LOGGER.info('ENABLED %s $%s', mode, _env)
    else:
        os.environ[_env] = '1'
        _LOGGER.info('DISABLED %s $%s', mode, _env)
