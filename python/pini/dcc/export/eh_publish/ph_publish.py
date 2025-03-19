"""Tools for managing simple access to publish command."""

import logging

from pini import dcc

_LOGGER = logging.getLogger(__name__)


def publish(version_up=False, export_abc=False, export_fbx=False, force=False):
    """Publish the current scene.

    Args:
        version_up (bool): version up after publish
        export_abc (bool): export abc
        export_fbx (bool): export fbx
        force (bool): replace existing without confirmation

    Returns:
        (CPOutput list): generated outputs
    """
    _LOGGER.info('PUBLISH')

    _handler = dcc.find_export_handler('basic')
    _LOGGER.info(' - HANDLER %s', _handler)
    return _handler.publish(
        version_up=version_up, export_abc=export_abc, export_fbx=export_fbx,
        force=force)
