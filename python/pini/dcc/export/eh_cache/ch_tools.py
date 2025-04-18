"""Tools for managing the function access to cache handler."""

import logging

from pini import dcc

_LOGGER = logging.getLogger(__name__)


def abc_cache(cacheables, **kwargs):
    """Execute cache operation.

    Args:
        cacheables (Cacheable list): items to cache
        force (bool): replace existing without confirmation

    Returns:
        (CPOutput list): caches
    """
    _LOGGER.info('ABC CACHE')
    _exporter = dcc.find_export_handler('AbcCache')
    _LOGGER.info('- EXPORTER %s', _exporter)
    return _exporter.exec(cacheables, **kwargs)


def fbx_cache(cacheables, **kwargs):
    """Execute cache operation.

    Args:
        cacheables (Cacheable list): items to cache
        force (bool): replace existing without confirmation

    Returns:
        (CPOutput list): caches
    """
    _LOGGER.info('FBX CACHE')
    _exporter = dcc.find_export_handler('FbxCache')
    _LOGGER.info('- EXPORTER %s', _exporter)
    return _exporter.exec(cacheables, **kwargs)
