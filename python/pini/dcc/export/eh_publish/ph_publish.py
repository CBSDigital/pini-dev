"""Tools for managing simple access to publish command."""

import logging

from pini import dcc

_LOGGER = logging.getLogger(__name__)


def lookdev_publish(version_up=False, force=False):
    """Lookdev publish current scene.

    Args:
        version_up (bool): version up after publish
        force (bool): replace existing without confirmation

    Returns:
        (CPOutput list): generated outputs
    """
    _LOGGER.info('MODEL PUBLISH')
    _exporter = dcc.find_export_handler('LookdevPublish')
    _LOGGER.info(' - EXPORTER %s', _exporter)
    return _exporter.publish(
        version_up=version_up, force=force)


def model_publish(
        notes=None, version_up=False, export_abc=False, export_fbx=False,
        force=False):
    """Model publish current scene.

    Args:
        notes (str): publish notes
        version_up (bool): version up after publish
        export_abc (bool): export abc
        export_fbx (bool): export fbx
        force (bool): replace existing without confirmation

    Returns:
        (CPOutput list): generated outputs
    """
    _LOGGER.info('MODEL PUBLISH')
    _exporter = dcc.find_export_handler('ModelPublish')
    _LOGGER.info(' - EXPORTER %s', _exporter)
    return _exporter.publish(
        version_up=version_up, export_abc=export_abc, export_fbx=export_fbx,
        force=force, notes=notes)


def publish(
        notes=None, version_up=False, export_abc=False, export_fbx=False,
        force=False):
    """Publish the current scene.

    Args:
        notes (str): publish notes
        version_up (bool): version up after publish
        export_abc (bool): export abc
        export_fbx (bool): export fbx
        force (bool): replace existing without confirmation

    Returns:
        (CPOutput list): generated outputs
    """
    _LOGGER.info('PUBLISH')
    _exporter = dcc.find_export_handler('basic')
    _LOGGER.info(' - EXPORTER %s', _exporter)
    return _exporter.publish(
        version_up=version_up, export_abc=export_abc, export_fbx=export_fbx,
        force=force, notes=notes)
