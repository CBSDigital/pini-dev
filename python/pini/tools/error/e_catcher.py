"""Tools for managing the error catcher decorator."""

import functools
import logging
import os
import sys

from pini.utils import File, abs_path

_LOGGER = logging.getLogger(__name__)


def _is_disabled():
    """Check whether the error catcher is disabled.

    Returns:
        (bool): whether disabled
    """
    return os.environ.get('PINI_DISABLE_ERROR_CATCHER') == '1'


def get_catcher(parent=None, qt_safe=False, supress_error=False):
    """Build error catcher decorator.

    Args:
        parent (QDialog): override parent dialog
        qt_safe (bool): make catcher safe to run in qt thread
        supress_error (bool): supress error on exception

    Returns:
        (fn): error catcher decorator
    """

    def _catch_decorator(func):

        @functools.wraps(func)
        def _catch_error_func(*args, **kwargs):

            from pini import dcc

            if _is_disabled() or dcc.batch_mode():
                return func(*args, **kwargs)

            # Run the function and catch any errors
            try:
                _result = func(*args, **kwargs)
            except Exception as _exc:  # pylint: disable=broad-exception-caught
                return _handle_exception(
                    _exc, parent=parent, qt_safe=qt_safe,
                    supress_error=supress_error)

            return _result

        return _catch_error_func

    return _catch_decorator


def _handle_exception(exc, parent, qt_safe, supress_error):
    """Handle an exception raised inside the error catcher.

    Args:
        exc (Exception): exception that was raised
        parent (QDialog): override parent dialog
        qt_safe (bool): make catcher safe to run in qt thread
        supress_error (bool): supress error on exception
    """
    from pini import qt, dcc
    from pini.tools import error

    from . import e_error, e_dialog

    _error = e_error.PEError()
    _show_traceback = False

    if isinstance(exc, qt.DialogCancelled):
        _LOGGER.info('DIALOG CANCELLED')
    elif isinstance(exc, StopIteration):
        _LOGGER.info('STOP ITERATION')

    elif isinstance(exc, error.HandledError):
        _title = exc.title or 'Error'
        qt.notify(str(exc), title=_title, icon=exc.icon, parent=parent)

    elif isinstance(exc, error.FileError):
        _LOGGER.info(' - FILE ERROR %s', exc)
        File(exc.file_).edit(line_n=exc.line_n)

    elif isinstance(exc, SyntaxError):
        _LOGGER.info('SYNTAX ERROR %s', exc)
        _file = File(abs_path(exc.filename))
        _line_n = int(str(exc).split()[-1].strip(')'))
        _LOGGER.info(' - LINE N %d', _line_n)
        _file.edit(line_n=_line_n)

    else:
        error.TRIGGERED = True
        e_dialog.launch_ui(_error, parent=parent)
        _show_traceback = True

    if _show_traceback:
        print(_error.to_text())

    # Finalise error
    if supress_error:
        return
    if qt_safe or dcc.NAME != 'maya':
        raise exc
    sys.exit()


def catch(func, supress_error=False):
    """Basic error catcher decorator.

    Args:
        func (fn): function to decorate
        supress_error (bool): supress error on exception

    Returns:
        (fn): decorated function
    """
    return get_catcher(supress_error=supress_error)(func)


def toggle(enabled=None):
    """Toggle error catcher on/off.

    Args:
        enabled (bool): state to apply
    """
    _enable = _is_disabled() if enabled is None else enabled
    if _enable:
        if 'PINI_DISABLE_ERROR_CATCHER' in os.environ:
            del os.environ['PINI_DISABLE_ERROR_CATCHER']
        _LOGGER.info('ERROR CATCHER ENABLED')
    else:
        os.environ['PINI_DISABLE_ERROR_CATCHER'] = '1'
        _LOGGER.info('ERROR CATCHER DISABLED')
