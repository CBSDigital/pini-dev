"""Tools for managing simple access to publish command."""

import logging

from pini import dcc
from pini.tools import release

_LOGGER = logging.getLogger(__name__)


@release.transfer_kwarg_docs(
    mod='pini.dcc.export', func='CMayaLookdevPublish.export')
def lookdev_publish(**kwargs):
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
    return _exporter.exec(**kwargs)


@release.transfer_kwarg_docs(
    mod='pini.dcc.export', func='CMayaModelPublish.export')
def model_publish(**kwargs):
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
    return _exporter.exec(**kwargs)


@release.transfer_kwarg_docs(
    mod='pini.dcc.export', func='CMayaBasicPublish.export')
def publish(**kwargs):
    """Publish the current scene.

    Returns:
        (CPOutput list): generated outputs
    """
    _LOGGER.info('PUBLISH')
    _exporter = dcc.find_export_handler('basic')
    _LOGGER.info(' - EXPORTER %s', _exporter)
    return _exporter.exec(**kwargs)
