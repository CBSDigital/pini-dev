"""General maya pipeline utilities."""

import logging

from maya import cmds

from pini.utils import single

from maya_pini import open_maya as pom

_LOGGER = logging.getLogger(__name__)


def find_cache_set(catch=True):
    """Find cache set from the current scene.

    This is for use in an asset scene, where a single cache set (referenced
    or not referenced) should be present.

    Args:
        catch (bool): no error if no cache set found

    Returns:
        (CNode): cache set
    """
    return single(pom.find_nodes(
        clean_name='cache_SET', type_='objectSet'), catch=catch)


def read_cache_set(mode='geo'):
    """Read cache set contents.

    Args:
        mode (str): content to find (geo/lights)

    Returns:
        (CNode list): cache set contents
    """
    _LOGGER.debug('READ CACHE SET')
    _set = find_cache_set()
    _LOGGER.debug(' - SET %s', _set)

    # Read contents
    _nodes = set()
    if _set:
        for _root in cmds.sets(_set, query=True) or []:
            _nodes.add(_root)
            _children = cmds.listRelatives(
                _root, allDescendents=True, type='transform', path=True) or []
            _nodes |= set(_children)
            _LOGGER.debug(' - ROOT %s %s', _root, _children)
    _LOGGER.debug(' - NODES %s', _nodes)

    # Apply mode filter
    _results = []
    for _node in sorted(_nodes):
        _node = pom.cast_node(_node)
        _LOGGER.debug(' - NODE %s %s', _node, type(_node).__name__)
        if mode == 'geo':
            if not isinstance(_node, pom.CMesh):
                continue
        elif mode == 'lights':
            if not _node.shp:
                continue
            _type = _node.shp.object_type()
            _LOGGER.debug('   - TYPE %s', _type)
            if _type not in ['VRayLightSphereShape']:
                continue
        else:
            raise NotImplementedError(mode)
        _results.append(_node)

    return _results
