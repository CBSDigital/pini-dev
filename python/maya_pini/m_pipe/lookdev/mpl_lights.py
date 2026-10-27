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

    _lgts = []

    # Read cache set lights
    _cache_set = mp_utils.find_cache_set(task='lookdev')
    _cache_set_lights = mp_utils.read_cache_set('lights', set_=_cache_set)
    _LOGGER.debug(' - FOUND %d CACHE SET LIGHTS', len(_cache_set_lights))
    _lgts += _cache_set_lights

    # Read mesh lights
    _mesh_lights = read_mesh_lights(fmt='node')
    _LOGGER.debug(' - FOUND %d MESH LIGHTS', len(_mesh_lights))
    _lgts += _mesh_lights

    if lights is True and not _lgts:
        raise RuntimeError('No lights found in scene')

    return _lgts


def read_mesh_lights(fmt='clean'):
    """Read mesh lights in the current scene.

    Args:
        fmt (str): results to return
            clean - cleaned string results for metadata
            node - CTransform node references

    Returns:
        (dict): lights + geos
    """
    from . import mpl_publish

    _LOGGER.debug('READ MESH LIGHTS %s', fmt)
    _geos = mpl_publish.read_shader_assignments(fmt='geo')

    _mesh_lgts_s = {}
    _mesh_lgts_n = {}

    # Find rs physical lights
    _rspls = []
    if cmds.pluginInfo('redshift4maya', query=True, loaded=True):
        _rspls = pom.find_nodes(type_='RedshiftPhysicalLight')
    for _lgt_s in _rspls:
        _LOGGER.debug(' - CHECK LIGHT SHAPE %s', _lgt_s)
        _lgt_t = _lgt_s.to_parent()
        _LOGGER.debug('   - LGT %s', _lgt_t)
        _mesh = _lgt_s.plug['areaShapeObject'].find_incoming(plugs=False)
        _LOGGER.debug('   - MESH %s', _mesh)
        if not _mesh:
            continue
        if _mesh not in _geos:
            continue
        _LOGGER.info('   - VALID MESH LIGHT')
        _mesh_lgts_n[_lgt_t] = _mesh
        _mesh_lgts_s[str(_lgt_t)] = to_clean(_mesh)

    # Format results
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

    _nodes = set()
    _top_node = mpl_publish.obt_top_node()

    # Move any lights in cache set into group
    _lights_grp = None
    _lights = read_lights()
    _LOGGER.debug(' - LIGHTS %s', _lights)
    for _light in _lights:
        _LOGGER.debug('   - ADD LIGHT %s', _light)
        if '|' in str(_light):
            _light = pom.CTransform(fix_dup_name(_light))
        _lights_grp = _light.add_to_grp('LIGHTS', col='Orange')
        _shd_grp = _lights_grp.add_to_grp(_top_node)

        _nodes |= {_light, mp_utils.to_light_shp(_light), _lights_grp, _shd_grp}

    return _nodes
