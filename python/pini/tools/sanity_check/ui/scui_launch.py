"""Tools for launching SanityCheck ui."""

import functools
import os

from pini import qt, pipe
from pini.tools import usage

from . import scui_dialog


def _launch(
        mode='standalone', checks=None, run=True, close_on_success=False,
        reset_pipe_cache=True, filter_=None, force=False):
    """Launch the sanity check interface.

    Args:
        mode (str): run in standalone or export mode
        checks (SCCheck list): override checks
        run (bool): automatically run checks on launch
        close_on_success (bool): close dialog on all checks passed
        reset_pipe_cache (bool): reset pipeline cache on launch
        filter_ (str): apply filter based on check name
        force (bool): in export mode force export ignoring any issues

    Returns:
        (SanityCheckUi): interface instance
    """
    from pini.tools import sanity_check, helper

    # Reset pipeline cache
    if reset_pipe_cache:
        if helper.is_active():
            helper.DIALOG.reset()
        else:
            pipe.CACHE.reset()

    # Launch
    sanity_check.DIALOG = scui_dialog.SanityCheckUi(
        mode=mode, checks=checks, run=run, close_on_success=close_on_success,
        force=force, filter_=filter_)
    return sanity_check.DIALOG


def launch_export_ui(
        mode, checks=None, reset_pipe_cache=True, filter_=None, force=False):
    """Launch SanityCheck in export mode.

    Args:
        mode (str): export mode (eg. publish/render) - this only affects
            button labels
        checks (SCCheck list): override checks
        reset_pipe_cache (bool): reset pipeline cache on launch
        filter_ (str): apply filter based on check name
        force (bool): force export ignoring any issues

    Returns:
        (dict): sanity check results
    """
    if os.environ.get('PINI_DISABLE_SANITY_CHECK'):
        return {'disabled': True}

    _dialog = _launch(
        mode=mode, close_on_success=True, checks=checks, force=force,
        reset_pipe_cache=reset_pipe_cache, filter_=filter_)
    if not _dialog.results:
        raise qt.DialogCancelled
    _results = {'checks': _dialog.results,
                'disabled': False}

    return _results


@functools.wraps(_launch)
@usage.get_tracker(name='SanityCheck')
def launch_ui(**kwargs):
    """Launch standalone SanityCheck ui.

    Returns:
        (SanitCheckUi): dialog
    """
    return _launch(**kwargs)
