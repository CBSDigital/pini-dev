"""General maya pipeline utilities."""

import copy
import logging

from maya import cmds

from pini.utils import single, passes_filter

from maya_pini import open_maya as pom
from maya_pini.utils import to_long

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
    if cmds.objExists('cache_SET'):
        return pom.cast_node('cache_SET')
    return single(pom.find_nodes(
        clean_name='cache_SET', type_='objectSet'), catch=catch)


def find_top_node():
    """Find geometry top node in the current scene.

    Returns:
        (CTransform): top node
    """

    _top_node = None
    _from_set = read_cache_set(mode='top')
    if _from_set and len(_from_set) == 1:
        _top_node = single(_from_set)

    _ref = pom.find_ref(catch=True)
    if _ref:
        return _ref.top_node
    _dag = pom.find_node(
        top_node=True, default=False, catch=True, filter_='-JUNK')
    if _dag:
        return _dag
    raise NotImplementedError('Failed to find top node')


def _read_cache_set_nodes(set_, mode, remove_junk=True):
    """Read cache set contents.

    Args:
        set_ (str): override set name
        mode (str): content to find
        remove_junk (bool): remove nodes in JUNK group

    Returns:
        (str list): set contents node names
    """
    _set = set_ or find_cache_set()
    _LOGGER.debug(' - SET %s', _set)

    # Read contents
    _nodes = set()
    if _set:
        for _root in cmds.sets(_set, query=True) or []:
            _nodes.add(_root)
            if mode == 'top':
                continue
            _children = cmds.listRelatives(
                _root, allDescendents=True, type='transform', path=True) or []
            _nodes |= set(_children)
            _LOGGER.debug(' - ROOT %s %s', _root, _children)
    _nodes = sorted(_nodes)

    if remove_junk:
        for _node in copy.copy(_nodes):
            _long = to_long(_node)
            if _long.startswith('|JUNK|'):
                _nodes.remove(_node)

    _LOGGER.debug(' - NODES %s', _nodes)

    return _nodes


def read_cache_set(  # pylint: disable=too-many-branches
        mode='geo', include_referenced=True, filter_=None, set_=None):
    """Read cache set contents.

    Args:
        mode (str): content to find
            all - all nodes
            top - top nodes only
            geo - only geometry nodes
            lights - only lights
            tfm - only transforms
        include_referenced (bool): include referenced geometry
        filter_ (str): apply node name filter
        set_ (str): override set name

    Returns:
        (CNode list): cache set contents
    """
    _LOGGER.debug('READ CACHE SET')

    # Apply mode filter
    _LOGGER.debug(' - APPLYING FILTERS refs=%d', include_referenced)
    _results = []
    for _node in _read_cache_set_nodes(set_=set_, mode=mode):

        if filter_ and not passes_filter(str(_node), filter_):
            continue

        try:
            _node = pom.cast_node(_node)
        except ValueError:
            _LOGGER.error('FAILED TO CAST NODE %s', _node)
            continue
        _LOGGER.debug(
            ' - NODE %s %s refd=%d shp=%s', _node, type(_node).__name__,
            _node.is_referenced(), _node.shp)

        if not include_referenced and _node.is_referenced():
            continue

        if mode in ('all', 'top'):
            pass
        elif mode == 'geo':
            if not isinstance(_node, pom.CMesh):
                continue
        elif mode == 'lights':
            if not to_light_shp(_node):
                continue
        elif mode in ('tfm', 'transforms'):
            if mode == 'transforms':
                from pini.tools import release
                release.apply_deprecation('04/03/25', 'Use tfm')
            if not isinstance(_node, pom.CBaseTransform):
                continue
        else:
            raise NotImplementedError(mode)

        _LOGGER.debug('   - ACCEPTED %s', _node)
        _results.append(_node)

    _LOGGER.debug(' - RESULTS %d %s', len(_results), _results)

    return _results


def to_light_shp(node):
    """Obtain light shape (if any) for the given node.

    In the case of redshift mesh lights, both the light and the mesh shapes
    are stored under the transform of the geometry. This function provides
    a single point of entry for obtaining the light shape.

    Args:
        node (CBaseTransform): transform to read shape from

    Returns:
        (CNode|None): light shape (if any)
    """
    _light_types = {
        'aiLightPortal',
        'VRayLightDomeShape',
        'VRayLightIESShape',
        'VRayLightRectShape',
        'VRayLightSphereShape',
        'VRaySunTarget',
    }
    _light_shps = []
    for _shp in node.to_shps():
        _type = _shp.object_type()
        if _type in _light_types or _type.endswith('Light'):
            _light_shps.append(_shp)
    return single(_light_shps, catch=True)
