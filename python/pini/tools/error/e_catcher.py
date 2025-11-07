"""Tools for managing the error catcher decorator."""

import functools
import logging
import sys

from pini.utils import File, abs_path

from . import e_tools

_LOGGER = logging.getLogger(__name__)
_CATCHING_ERROR = False


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

            global _CATCHING_ERROR

            # Prevent catcher nesting, only execute outer catcher
            if _CATCHING_ERROR:
                return func(*args, **kwargs)
            _CATCHING_ERROR = True

            _LOGGER.debug('CATCH ERROR FUNC %s', func)

            from pini import dcc

            if e_tools.is_disabled() or dcc.batch_mode():
                return func(*args, **kwargs)

            # Run the function and catch any errors
            _LOGGER.debug(' - EXEC FUNC %s', func)
            try:
                _result = func(*args, **kwargs)
            except Exception as _exc:  # pylint: disable=broad-exception-caught
                _LOGGER.debug(' - FUNC ERRORED %s', _exc)
                return _handle_exception(
                    _exc, parent=parent, qt_safe=qt_safe,
                    supress_error=supress_error)
            finally:
                _CATCHING_ERROR = False

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
    _check_for_modal_progress()

    if isinstance(exc, qt.DialogCancelled):
        _LOGGER.info(' - DIALOG CANCELLED')
    elif isinstance(exc, StopIteration):
        _LOGGER.info(' - STOP ITERATION')

    elif isinstance(exc, error.HandledError):
        _title = exc.title or 'Error'
        _parent = exc.parent or parent
        _LOGGER.info(' - HANDLED ERROR %s', _parent)
        qt.notify(
            str(exc), title=_title, icon=exc.icon, parent=_parent)

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
        _LOGGER.warning(' - LAUNCHING ERROR DIALOG')
        e_dialog.launch_ui(_error, parent=parent)
        _show_traceback = True

    _LOGGER.debug(' - SHOW TRACEBACK %d', _show_traceback)
    if _show_traceback:
        print(_error.to_text())

    # Finalise error
    if supress_error:
        _LOGGER.debug(' - SUPRESS ERROR')
        return
    if qt_safe or dcc.NAME not in ('maya', 'hou'):
        _LOGGER.debug(' - RAISING EXC')
        raise exc
    _LOGGER.debug(' - APPLY sys.exit')
    sys.exit()


def _check_for_modal_progress():
    """Check for modal progress dialog.

    If there is a progress dialog locking the interface then this should
    be closed in the case of an error, otherwise the error dialog will
    be blocked.
    """
    from pini import qt
    _LOGGER.debug(' - CHECK MODAL PROGRESS %s', qt.MODAL_PROGRESS_BAR)
    if qt.MODAL_PROGRESS_BAR:
        qt.MODAL_PROGRESS_BAR.close()


def catch(func, supress_error=False):
    """Basic error catcher decorator.

    Args:
        func (fn): function to decorate
        supress_error (bool): supress error on exception

    Returns:
        (fn): decorated function
    """
    return get_catcher(supress_error=supress_error)(func)
