"""Tools for managing the error catcher decorator."""

import functools
import logging
import os
import sys

_LOGGER = logging.getLogger(__name__)


def _is_disabled():
    """Check whether the error catcher is disabled.

    Returns:
        (bool): whether disabled
    """
    return os.environ.get('PINI_DISABLE_ERROR_CATCHER') == '1'


def get_catcher(parent=None, qt_safe=False):
    """Build error catcher decorator.

    Args:
        parent (QDialog): override parent dialog
        qt_safe (bool): make catcher safe to run in qt thread

    Returns:
        (fn): error catcher decorator
    """

    def _catch_decorator(func):

        @functools.wraps(func)
        def _catch_error_func(*args, **kwargs):

            from pini import qt, dcc, icons
            from pini.tools import error

            if _is_disabled() or dcc.batch_mode():
                return func(*args, **kwargs)

            # Run the function and catch any errors
            try:
                _result = func(*args, **kwargs)
            except qt.DialogCancelled as _exc:
                if qt_safe or dcc.NAME != 'maya':
                    raise _exc
                sys.exit()
            except error.HandledError as _exc:
                _title = _exc.title or 'Error'
                qt.notify(str(_exc), title=_title,
                          icon=icons.find('Hot Pepper'))
                if qt_safe or dcc.NAME != 'maya':
                    raise _exc
                sys.exit()
            except Exception as _exc:  # pylint: disable=broad-exception-caught
                from . import ce_error, ce_dialog
                error.TRIGGERED = True
                _error = ce_error.CEError()
                ce_dialog.launch_ui(_error, parent=parent)
                if qt_safe or dcc.NAME != 'maya':
                    raise _exc
                print(_error.to_text())
                sys.exit()
            return _result

        return _catch_error_func

    return _catch_decorator


def catch(func):
    """Basic error catcher decorator.

    Args:
        func (fn): function to decorate

    Returns:
        (fn): decorated function
    """
    return get_catcher()(func)


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
