"""Tools for managing deferred evaluation."""

import logging
import time

import maya

from maya import cmds

_LOGGER = logging.getLogger(__name__)


def process_deferred_events(max_iterations=1000, catch=False):
    """Wait until all events in evalDeferred list have been processed.

    Args:
        max_iterations (int): number of iterations before fail
        catch (bool): no error on overflow
    """
    _start = time.time()
    _n_events = 0
    _events = None

    # Wait for events to process
    for _idx in range(max_iterations):
        _events = [
            _event for _event in cmds.evalDeferred(list=True)
            if _event != '<internal command>']
        if not _idx and not _events:
            return
        _n_events = max(_n_events, len(_events))
        if not _events:
            break
        _LOGGER.debug(' - EVENTS %d %d %s', _idx, len(_events), _events)
        maya.utils.processIdleEvents()

    else:
        _msg = f'Failed to process evalDeferred stack {_events}'
        if catch:
            _LOGGER.error(_msg)
            return
        raise RuntimeError(_msg)

    _LOGGER.info(
        ' - WAITED FOR evalDeferred STACK TO PROCESS (%.01fs - %d events '
        '- %d iterations)',
        time.time() - _start, _n_events, _idx)
