"""Tools for managing lookdev lights."""

import logging

from maya import cmds


from maya_pini import open_maya as pom
from maya_pini.utils import to_clean, fix_dup_name

from .. import mp_utils

_LOGGER = logging.getLogger(__name__)


def read_lights(lights=None):
    """Read lights in the current scene.

    Args:
        lights (str): whether lights have been requested by exporter
            True - lights required
            False - ignore lights
            None - add lights if available

    Returns:
        (CTransform list): lights
    """
    _LOGGER.debug('READ LIGHTS')

    if lights is False:
        return []

    _lgts = set()

    # Read cache set lights
    _cache_set = mp_utils.find_cache_set(task='lookdev')
    _cache_set_lights = mp_utils.read_cache_set('lights', set_=_cache_set)
    _LOGGER.debug(' - FOUND %d CACHE SET LIGHTS', len(_cache_set_lights))
    _lgts |= set(_cache_set_lights)

    # Read mesh lights
    _mesh_lights = read_mesh_lights(fmt='node')
    _LOGGER.debug(' - FOUND %d MESH LIGHTS', len(_mesh_lights))
    _lgts |= set(_mesh_lights)

    if lights is True and not _lgts:
        raise RuntimeError('No lights found in scene')

    return sorted(_lgts)


def read_mesh_lights(fmt='clean', filter_=None):
    """Read mesh lights in the current scene.

    Args:
        fmt (str): results to return
            clean - cleaned string results for metadata
            node - CTransform node references
        filter_ (str): apply light name filter (for debugging)

    Returns:
        (dict): lights + geos
    """
    from maya_pini import m_pipe

    _LOGGER.debug('READ MESH LIGHTS %s', fmt)
    _tfms = m_pipe.read_cache_set('tfm')

    _mesh_lgts_n = {}  # Mesh light nodes

    # Find rs physical lights
    _rspls = []
    if cmds.pluginInfo('redshift4maya', query=True, loaded=True):
        _rspls = pom.find_nodes(
            type_='RedshiftPhysicalLight', filter_=filter_)
    _LOGGER.debug(' - RS PHYSICAL LIGHTS %s', _rspls)
    for _lgt_s in _rspls:
        _LOGGER.debug('   - CHECK LIGHT SHAPE %s', _lgt_s)
        _lgt_t = _lgt_s.to_parent()
        _LOGGER.debug('     - LGT %s', _lgt_t)
        _mesh_t = _lgt_s.plug['areaShapeObject'].find_incoming(plugs=False)
        _LOGGER.debug('     - MESH %s', _mesh_t)
        if not _mesh_t:
            continue
        if _mesh_t not in _tfms:
            _LOGGER.info('     - MESH NOT IN TFMS')
            continue
        _LOGGER.info('   - VALID MESH LIGHT')
        _mesh_lgts_n[_lgt_t] = _mesh_t

    # Find vray light meshes
    _vrlms = []
    if cmds.pluginInfo('redshift4maya', query=True, loaded=True):
        _vrlms = pom.find_nodes(
            type_='VRayLightMesh', filter_=filter_)
    _LOGGER.debug(' - VR LIGHT MESHES %s', _vrlms)
    for _vrlm in _vrlms:
        _LOGGER.debug('   - CHECK LIGHT MESH %s', _vrlm)
        _mesh_t = _vrlm.plug['dagSetMembers'].find_incoming(plugs=False)
        _LOGGER.debug('     - MESH %s', _mesh_t)
        _mesh_lgts_n[_vrlm] = _mesh_t

    # Format results
    _mesh_lgts_s = {
        to_clean(_lgt_t): to_clean(_mesh)
        for _lgt_t, _mesh in _mesh_lgts_n.items()}
    if fmt == 'clean':
        _result = _mesh_lgts_s
    elif fmt == 'node':
        _result = _mesh_lgts_n
    else:
        raise ValueError(fmt)

    return _result


def setup_lights():
    """Setup lights for export.

    Returns:
        (str set): lights nodes
    """
    from . import mpl_publish

    _LOGGER.debug('SETUP LIGHTS')
    _nodes = set()
    _top_node = mpl_publish.obt_top_node()
    _lights_grp = None
    _lights = read_lights()

    # Move any lights in cache set into group
    _LOGGER.debug('🍎 SETUP LIGHTS FOR EXPORT')
    _LOGGER.debug(' - LIGHTS %s', _lights)
    for _light in _lights:

        _type = _light.object_type()
        _LOGGER.debug('   - ADD LIGHT %s %s', _light, _type)

        if '|' in str(_light):
            _light = pom.cast_node(fix_dup_name(_light))
        _nodes.add(_light)

        # Detatch vray lights (no tfm required)
        if _type == 'VRayLightMesh':
            for _attr in ['dagSetMembers[0]', 'lightlinkConnection']:
                _light.plug[_attr].break_conns()

        # Otherwise move to lights grp to save tfm/shp
        else:
            _lights_grp = _light.add_to_grp('LIGHTS', col='Orange')
            _shd_grp = _lights_grp.add_to_grp(_top_node)
            _nodes |= {mp_utils.to_light_shp(_light), _lights_grp, _shd_grp}

    return _nodes
