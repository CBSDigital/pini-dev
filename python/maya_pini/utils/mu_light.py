"""General utilities relating to lights."""

import logging
import operator

from maya import cmds

from . import mu_misc

_LOGGER = logging.getLogger(__name__)
_TYPES_CACHE = {}


def find_light_types():
    """Find types of light.

    Returns:
        (str list): type names
    """
    _key = tuple(
        cmds.pluginInfo(_plugin, query=True, loaded=True)
        for _plugin in ('control', 'mtoa', 'vrayformaya', 'redshift4maya'))
    _LOGGER.debug(' - KEY %s', _key)

    if _key not in _TYPES_CACHE:
        _types = sorted([
            _type for _type in cmds.allNodeTypes()
            if _type.endswith('Light') or
            _type.startswith('VRayLight') or
            _type.startswith('aiLight')],
            key=operator.methodcaller('lower'))
        _LOGGER.debug(' - READ TYPES %d %s', len(_types), _types)
        _TYPES_CACHE[_key] = _types

    return _TYPES_CACHE[_key]


def find_lights(referenced=None):
    """Find lights in the current scene.

    Args:
        referenced (bool): filter by referenced state

    Returns:
        (str list): matching lights
    """
    _lgts = cmds.ls(type=find_light_types())
    if referenced is not None:
        _lgts = [
            _lgt for _lgt in _lgts
            if cmds.referenceQuery(_lgt, isNodeReferenced=True) == referenced]
    return _lgts


def node_is_light(node):
    """Test if the given node is a light.

    If the node is a transform, its shape is read.

    Args:
        node (str): node to test

    Returns:
        (bool): whether node is a light
    """
    _LOGGER.info('NODE IS LIGHT %s', node)
    _type = cmds.objectType(node)
    if _type == 'transform':
        _shp = mu_misc.to_shp(node)
        _type = cmds.objectType(_shp)
    _LOGGER.info(' - TYPE %s', _type)
    return _type in find_light_types()
