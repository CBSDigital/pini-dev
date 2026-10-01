"""Tools for launching SanityCheck ui."""

import functools
import os

from pini import qt, pipe
from pini.tools import usage

from . import scui_dialog


def _launch(
        mode='standalone', checks=None, run=True, close_on_success=False,
        reset_pipe_cache=True, filter_=None, task=None, modal=None,
        exporter=None, parent=None, force=False):
    """Launch the sanity check interface.

    Args:
        mode (str): run in standalone or export mode
        checks (SCCheck list): override checks
        run (bool): automatically run checks on launch
        close_on_success (bool): close dialog on all checks passed
        reset_pipe_cache (bool): reset pipeline cache on launch
        filter_ (str): apply filter based on check name
        task (str): task to apply checks filter to
        modal (bool): override default modal state
        exporter (CExporter): exported that launched sanity check
        parent (QDialog): parent dialog
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
        force=force, filter_=filter_, task=task, modal=modal, parent=parent,
        exporter=exporter)
    return sanity_check.DIALOG


def launch_export_ui(
        exporter, checks=None, reset_pipe_cache=True, filter_=None, task=None,  # pylint: disable=unused-argument
        close_on_success=True, modal=None, parent=None, force=False):
    """Launch SanityCheck in export mode.

    Args:
        exporter (CExporter): exported that requesting sanity checks
        checks (SCCheck list): override checks
        reset_pipe_cache (bool): reset pipeline cache on launch
        filter_ (str): apply filter based on check name
        task (str): task to apply checks filter to
        close_on_success (bool): close dialog on all checks passed
        modal (bool): override default modal state
        parent (QDialog): parent dialog
        force (bool): force export ignoring any issues

    Returns:
        (dict): sanity check results
    """
    if os.environ.get('PINI_DISABLE_SANITY_CHECK'):
        return {'disabled': True}

    _dialog = _launch(
        mode='export', close_on_success=close_on_success,
        checks=checks, force=force, reset_pipe_cache=reset_pipe_cache,
        filter_=filter_, parent=parent, modal=modal, exporter=exporter)
    if not _dialog.results:
        raise qt.DialogCancelled
    _checks_data = {
        'checks': _dialog.results,
        'disabled': False}

    return _checks_data


@functools.wraps(_launch)
@usage.get_tracker(name='SanityCheck')
def launch_ui(**kwargs):
    """Launch standalone SanityCheck ui.

    Returns:
        (SanitCheckUi): dialog
    """
    return _launch(**kwargs)
