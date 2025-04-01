"""Tools for managing the error catcher decorator."""

import functools
import logging
import sys

from pini.utils import File, abs_path

from . import e_tools

_LOGGER = logging.getLogger(__name__)


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

            if e_tools.is_disabled() or dcc.batch_mode():
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

    _LOGGER.debug('HANDLE EXCEPTION %s', exc)
    _error = e_error.PEError()
    _show_traceback = False

    if isinstance(exc, qt.DialogCancelled):
        _LOGGER.info(' - DIALOG CANCELLED')
    elif isinstance(exc, StopIteration):
        _LOGGER.info(' - STOP ITERATION')

    elif isinstance(exc, error.HandledError):
        _title = exc.title or 'Error'
        qt.notify(
            str(exc), title=_title, icon=exc.icon,
            parent=exc.parent or parent)

    elif (
            isinstance(exc, error.FileError) and
            not e_tools.is_disabled('FileError')):
        _LOGGER.info(' - FILE ERROR %s', exc)
        File(exc.file_).edit(line_n=exc.line_n)

    elif isinstance(exc, SyntaxError):
        _LOGGER.info(' - SYNTAX ERROR %s', exc)
        _file = File(abs_path(exc.filename))
        _line_n = int(str(exc).split()[-1].strip(')'))
        _LOGGER.info(' - LINE N %d', _line_n)
        _file.edit(line_n=_line_n)

    else:
        _LOGGER.debug(' - BASIC ERROR')
        error.TRIGGERED = True
        e_dialog.launch_ui(_error, parent=parent)
        _show_traceback = True

    _LOGGER.debug(' - SHOW TRACEBACK %d', _show_traceback)
    if _show_traceback:
        print(_error.to_text())

    # Finalise error
    if supress_error:
        return
    if qt_safe or dcc.NAME not in ('maya', 'hou'):
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
