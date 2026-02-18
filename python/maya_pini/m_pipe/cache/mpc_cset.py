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

    def __init__(self, cache_set, extn):
        """Constructor.

        Args:
            cache_set (str): custom cache set node
            extn (str): cache output extension
        """
        assert cache_set.endswith('_CSET')

        if cmds.referenceQuery(cache_set, isNodeReferenced=True):
            raise ValueError(
                f'Referenced CSETs not supported {cache_set}')
        self.cache_set = cache_set

        _output_name = self.cache_set.replace('_CSET', '')
        super().__init__(
            output_name=_output_name, label=f'{_output_name} (CSET)',
            output_type='geo', node=self.cache_set, extn=extn,
            src_ref=None)

        if not self.to_geo():
            raise ValueError('No export geo')
        try:
            self.output
        except ValueError as _exc:
            raise ValueError(
                'Failed to map to abc ' + self.output_name) from _exc

    def _set_name(self, name):
        """Rename this cacheable.

        Args:
            name (str): new name to apply
        """
        raise NotImplementedError

    def select_in_scene(self):
        """Select this set in the current scene."""
        cmds.select(self.cache_set)

    def to_geo(self, extn='abc'):  # pylint: disable=unused-argument
        """Obtain list of geo in cache set.

        Args:
            extn (str): output extension

        Returns:
            (str list): geo
        """
        return _read_cset_geo(self.cache_set)

    def _to_icon(self):
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


def find_csets(extn='abc'):
    """Find cache sets in the current scene.

    Args:
        extn (str): cache output extension

    Returns:
        (CPCacheableSet list): cacheable sets
    """
    _csets = []
    for _set in cmds.ls(type='objectSet'):
        if not _set.endswith('_CSET'):
            continue
        try:
            _cset = CPCacheableSet(_set, extn=extn)
        except ValueError:
            continue
        _csets.append(_cset)
    return _csets
