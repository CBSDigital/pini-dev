"""Tools for managing the function access to cache handler."""

import logging

from pini import dcc

_LOGGER = logging.getLogger(__name__)


def abc_cache(cacheables, force=False):
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
    return _exporter.cache(cacheables, force=force)
