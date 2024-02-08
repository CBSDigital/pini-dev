"""Tools for managing caching of CSETs."""

import logging

from maya import cmds

from pini import icons

from . import mpc_cacheable

_LOGGER = logging.getLogger(__name__)


class CPCacheableSet(mpc_cacheable.CPCacheable):
    """Represents a custom cache set in the current scene.

    This is a set with _CSET suffix - eg. beachBall_CSET
    """

    def __init__(self, cache_set):
        """Constructor.

        Args:
            cache_set (str): custom cache set node
        """
        assert cache_set.endswith('_CSET')
        self.node = cache_set

        if cmds.referenceQuery(cache_set, isNodeReferenced=True):
            raise ValueError(
                'Referenced CSETs not supported {}'.format(cache_set))
        self.cache_set = cache_set
        self.output_name = self.cache_set.replace('_CSET', '')
        self.label = self.output_name+' (CSET)'
        self.output_type = 'geo'

        if not self.to_geo():
            raise ValueError('No export geo')
        try:
            self.to_output()
        except ValueError:
            raise ValueError('Failed to map to abc '+self.output_name)

    def rename(self, name):
        """Rename this cacheable.

        Args:
            name (str): new name to apply
        """
        raise NotImplementedError

    def select_in_scene(self):
        """Select this set in the current scene."""
        cmds.select(self.cache_set)

    def to_geo(self):
        """Obtain list of geo in cache set.

        Returns:
            (str list): geo
        """
        return _read_cset_geo(self.cache_set)

    def to_icon(self):
        """Get icon for this cache set.

        Returns:
            (str): path to icon
        """
        return icons.find('Urn')


def _read_cset_geo(cset):
    """Read geo from given CSET for AbcExport.

    Any object set children are read recursively and their contents added
    to the list as AbcExport does not support sets.

    Args:
        cset (str): cache set to read

    Returns:
        (str list): CSET geo
    """
    _items = []
    for _item in cmds.sets(cset, query=True) or []:
        if cmds.objectType(_item) == 'objectSet':
            _items += _read_cset_geo(_item)
        else:
            _items.append(_item)
    return _items


def find_csets():
    """Find cache sets in the current scene.

    Returns:
        (CPCacheableSet list): cacheable sets
    """
    _csets = []
    for _set in cmds.ls(type='objectSet'):
        if not _set.endswith('_CSET'):
            continue
        try:
            _cset = CPCacheableSet(_set)
        except ValueError:
            continue
        _csets.append(_cset)
    return _csets
