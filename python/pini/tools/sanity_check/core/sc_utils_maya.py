"""General utilies for sanity check in maya."""

import logging

from maya import cmds

from pini.utils import single, wrap_fn
from maya_pini.utils import to_shps, to_clean

from . import sc_check

_LOGGER = logging.getLogger(__name__)


class SCMayaCheck(sc_check.SCCheck):
    """Base class for any maya check.

    This adds a check shape method, so allow shape naming fails to be shared
    across muliple checks.
    """

    def run(self):
        """Execute this check."""
        raise NotImplementedError

    def _check_shp(self, node):
        """Check node shapes.

        Checks for multiple shape nodes and shape nodes not matching
        transform.

        Args:
            node (str): node to check
        """
        _shps = to_shps(node)
        if not _shps:
            return

        # Handle multiple shapes
        if len(_shps) > 1:
            _msg = 'Node {} has multiple shapes ({})'.format(
                node, '/'.join(_shps))
            self.add_fail(_msg, node=node)
            return

        # Check shape name
        _shp = single(_shps)
        _cur_shp = to_clean(_shp)
        _correct_shp = to_clean(node)+'Shape'
        if _cur_shp != _correct_shp:
            _fix = wrap_fn(cmds.rename, _shp, _correct_shp)
            _msg = (
                'Node {} has badly named shape node {} (should be '
                '{})'.format(node, _shp, _correct_shp))
            self.add_fail(_msg, fix=_fix, node=node)


def read_cache_set(mode='all', set_='cache_SET'):
    """Read cache set contents.

    Args:
        mode (str): type of object to read (eg. all/geo/mesh)
        set_ (str): override cache set (default is cache_SET)

    Returns:
        (str list): cache set contents
    """
    _LOGGER.debug('READ CACHE SET %s', set_)

    if not cmds.objExists(set_):
        _LOGGER.debug(' - MISSING CACHE SET')
        return []

    _all = []
    for _root in cmds.sets(set_, query=True) or []:
        _children = cmds.listRelatives(
            _root, allDescendents=True, path=True) or []
        _all += [_root] + _children
    _LOGGER.debug(' - FOUND %d NODES', len(_all))
    if mode == 'all':
        return _all

    _results = []
    for _node in _all:

        _type = cmds.objectType(_node)

        # See if node matches mode filter
        _match = False
        if (
                _type == 'transform' and
                mode == 'geo'):
            _shps = cmds.listRelatives(_node, shapes=True, path=True) or []
            if [_shp for _shp in _shps if cmds.objectType(_shp) == 'mesh']:
                _match = True
        elif _type == mode:
            _match = True

        if _match:
            _results.append(_node)

    return _results
