"""Tools for managing public render functions."""

import logging

from pini import dcc

_LOGGER = logging.getLogger(__name__)


def local_render(force=False):
    """Local render current scene.

    Args:
        force (bool): replace existing without confirmation
    """
    _LOGGER.info('LOCAL RENDER')
    _exporter = dcc.find_export_handler('LocalRender')
    _LOGGER.info(' - EXPORTER %s', _exporter)
    _exporter.render(camera='persp', mov=False, view=False, force=force)
