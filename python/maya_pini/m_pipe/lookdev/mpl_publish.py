"""Tools for managing lookdev publishes."""

import collections
import logging
import re

from maya import cmds

from pini import dcc
from pini.utils import passes_filter

from maya_pini import open_maya as pom, tex
from maya_pini.utils import to_clean, to_long, to_namespace, to_parent

from .. import mp_utils

_LOGGER = logging.getLogger(__name__)


def find_export_nodes(filter_=None):
    """Find nodes to export in lookdev mb file.

    Args:
        filter_ (str): apply name filter to the list of export names

    Returns:
        (str list): lookdev nodes
    """
    _export_nodes = set()

    # Add shaders
    for _shd, _data in read_shader_assignments().items():
        _export_nodes.add(_shd)
        _export_nodes.add(_data['shadingEngine'])

    # Add override sets
    if cmds.objExists('overrides_SET'):
        _export_nodes.add('overrides_SET')
    for _set, _ in read_override_sets().items():
        _export_nodes.add(_set)

    # Add top node if map attrs
    if _read_map_top_node_attrs():
        _dummy = _build_dummy_top_node()
        _export_nodes.add(_dummy)

    # Add lights
    _lights = mp_utils.read_cache_set(mode='lights')
    _export_nodes |= {_light.clean_name for _light in _lights}
    _export_nodes |= {
        mp_utils.to_light_shp(_light).clean_name for _light in _lights}

    if filter_:
        _export_nodes = [
            _node for _node in _export_nodes
            if passes_filter(str(_node), filter_)]
    _export_nodes = sorted(_export_nodes)
    _LOGGER.debug(' - EXPORT NODES %s', _export_nodes)

    return _export_nodes


def _build_dummy_top_node():
    """Build dummy top node to store top node attributes on.

    eg. colour switch on top node - the switch is stored on a dummy network
    node called DummyTopNode, and then transferred onto the target reference
    top node on attach.

    Returns:
        (CNode): dummy top node
    """
    _top_node = mp_utils.find_top_node()
    assert _top_node
    if cmds.objExists('DummyTopNode'):
        cmds.delete('DummyTopNode')
    _dummy = pom.CMDS.createNode('network', name='DummyTopNode')
    _LOGGER.info(' - DUMMY TOP NODE')
    for _attr in _read_map_top_node_attrs():
        _top_attr = _top_node.plug[_attr]
        _LOGGER.info(' - TOP NODE ATTR %s', _top_attr)
        _dummy_attr = _dummy.add_attr(
            _attr, _top_attr.get_val(), min_val=_top_attr.get_min(),
            max_val=_top_attr.get_max())
        _LOGGER.info('   - MAP %s -> %s', _top_node, _dummy_attr)
        _conns = _top_attr.find_outgoing()
        _LOGGER.info('     - CONNS %s', _conns)
        for _trg in _conns:
            _dummy_attr.connect(_trg, force=True)
    return str(_dummy)


def read_override_sets(crop_namespace=True):
    """Read override sets.

    This is any set contained in override_SET, or any RedshiftMeshParameters
    nodes if redshift is enabled.

    Args:
        crop_namespace (bool): remove namespace from geos

    Returns:
        (dict): set/geos
    """

    # Build list of sets to check
    _sets = set()
    if cmds.objExists('overrides_SET'):
        _over_set = pom.CNode('overrides_SET')
        _sets.add(_over_set)
        for _item in pom.CMDS.sets(_over_set, query=True):
            if _item.object_type() == 'objectSet':
                _sets.add(_item)
    if cmds.pluginInfo('redshift4maya', query=True, loaded=True):
        for _type in [
                'RedshiftMeshParameters',
                'RedshiftMatteParameters',
                'RedshiftVisibility']:
            _sets |= set(pom.find_nodes(type_=_type))

    # Read contents of sets
    _data = {}
    for _set in _sets:
        _geos = set()
        for _item in pom.CMDS.sets(_set, query=True):
            if _item.object_type() != 'objectSet':
                _geos.add(_item.clean_name if crop_namespace else _item)
        if not _geos:
            continue
        _data[str(_set)] = sorted(_geos)

    return _data


def _read_clean_shd_assignments():
    """Read relevant shaders from the current scene assignments.

    Returns:
        (dict): {shader: shading engine/geos} assignment data
    """
    _shds = {}
    for _shd, _data in read_shader_assignments(referenced=False).items():
        _data['geos'] = [to_clean(_geo) for _geo in _data['geos']]
        _shds[_shd] = _data
    return _shds


def _read_custom_aovs(sgs):
    """Read custom aovs set up in this scene.

    There are connected to the indexed aiCustomAOVs attribute on the
    shading group, each one having a name (aovName) and colour connection
    (aovInput). On reference, maya will automatically rebuild these
    connections if the aov exists in the current scene.

    However since, since they are stored as indexes, the reference
    edits can get confused, and end up being connected to the wrong
    aov name. To avoid this, the input connection and aov name are
    stored on lookdev publish.

    Args:
        sgs (str list): shading groups to check

    Returns:
        (tuple list): plug/name list
    """
    if not cmds.pluginInfo('mtoa', query=True, loaded=True):
        return []

    _LOGGER.debug('READ CUSTOM AOVS')
    _custom_aovs = []
    for _sg in sgs:
        _sg = pom.CNode(_sg)
        _LOGGER.debug(' - CHECKING SG %s', _sg)
        _conn = _sg.plug['aiCustomAOVs'].find_incoming(connections=True)
        if _conn:
            _src, _dest = _conn
            _, _idx, _ = re.split(r'[\[\]]', str(_dest))
            _idx = int(_idx)
            _name = _sg.attr[f'aiCustomAOVs[{_idx:d}].aovName']
            _aov = str(cmds.getAttr(_name))
            _custom_aovs.append((str(_src), str(_aov)))

    return _custom_aovs


def _read_geo_settings():
    """Read attribute setting overrides to apply to lighting scenes.

    Returns:
        (dict): settings data
    """
    _LOGGER.debug('READ SETTINGS')

    _settings = collections.defaultdict(dict)

    # Find shapes
    _shds = read_shader_assignments()
    _geos = sum([_data['geos'] for _data in _shds.values()], [])
    for _geo in _geos:

        _LOGGER.debug(' - CHECKING GEO %s', _geo)
        try:
            _geo = pom.CMesh(_geo)
        except ValueError:
            _LOGGER.debug('   - FAILED TO BUILD MESH')
            continue
        _LOGGER.debug('   - MESH %s %s', _geo, _geo.shp)
        if not _geo.shp:
            continue

        _attrs = []
        if 'arnold' in dcc.allowed_renderers():
            _attrs += [
                'aiOpaque',
                'aiSubdivIterations',
                'aiSubdivType']
        if 'vray' in dcc.allowed_renderers():
            _user_attrs = cmds.listAttr(_geo.shp, userDefined=True) or []
            _attrs += [
                _attr for _attr in _user_attrs
                if _attr.startswith('vray')]
        if 'redshift' in dcc.allowed_renderers():
            _attrs += [
                'rsEnableSubdivision',
                'rsEnableDisplacement']
            _LOGGER.debug(' - RS ATTRS %s', _attrs)

        # Read non-default settings
        for _attr in _attrs:
            if not _geo.shp.has_attr(_attr):
                continue
            _plug = _geo.shp.plug[_attr]
            _type = _plug.get_type()
            if _type in ('typed', ):
                continue
            _val = _plug.get_val()
            _def = _plug.get_default()
            if _val != _def:
                _settings[str(_geo)][_attr] = _val

    _settings = dict(_settings)
    return _settings


def _read_lights():
    """Read lights setting.

    If there are lights in the cache set, then these are stored in the
    lookdev publish, and this is flagged in the metadata.

    Returns:
        (bool): whether there are lights in cache set
    """
    return bool(mp_utils.read_cache_set(mode='lights'))


def _read_map_top_node_attrs():
    """Read any user defined top node attributes with outgoing connections.

    These are attributes are stored on a dummy top node, and then rebuild
    on the shaders target reference top node at on attach.

    Returns:
        (list): top node attributes to map
    """
    _attrs = []
    _top_node = mp_utils.find_top_node()
    if _top_node:
        for _plug in _top_node.list_attr(user_defined=True):
            if not _plug.find_outgoing():
                continue
            _attrs.append(_plug.attr)
    return _attrs


def read_publish_metadata():
    """Read all shading data to save to yml file.

    This includes shader assignments and settings overrides.

    Returns:
        (dict): shading data
    """
    _shds = _read_clean_shd_assignments()
    _sgs = [_shd_data['shadingEngine'] for _shd_data in _shds.values()]

    # Gather data
    _data = {}
    _data['shds'] = _shds
    _data['settings'] = _read_geo_settings()
    _data['custom_aovs'] = _read_custom_aovs(sgs=_sgs)
    _data['override_sets'] = read_override_sets()
    _data['lights'] = _read_lights()
    _data['top_node_attrs'] = _read_map_top_node_attrs()

    return _data


def read_shader_assignments(
        fmt='dict', allow_face_assign=False, referenced=None, filter_=None,
        catch=True):
    """Read shader assignments data.

    This data relates to the current scene. Namespaces are removed
    before it's written to disk.

    Args:
        fmt (str): results format
            dict - full shader details as dict
            shd - simple list of shaders
        allow_face_assign (bool): do not ignore face assignments (eg. for
            speed tree assets)
        referenced (bool): filter by shader referenced status
        filter_ (str): apply name filter
        catch (bool): no error if no shaders found

    Returns:
        (dict/list): shader assignments
    """
    _LOGGER.debug('READ SHD ASSIGNMENTS')

    # Read shading data
    _data = {}
    _ses = pom.find_nodes(type_='shadingEngine')
    _shds = []
    for _se in _ses:
        _shd, _shd_data = _read_se(
            engine=_se, referenced=referenced,
            allow_face_assign=allow_face_assign, filter_=filter_)
        if not _shd:
            continue
        _shds.append(_shd)
        _data[str(_shd)] = _shd_data

    if not catch and not _data:
        raise RuntimeError('No shader assignments found')

    # Build result
    if fmt == 'dict':
        _result = _data
    elif fmt == 'shd':
        _result = _shds
    else:
        raise NotImplementedError(fmt)
    return _result


def _read_se(engine, referenced, allow_face_assign, filter_):
    """Read shading engine.

    Args:
        engine (CNode): shading engine
        referenced (bool): filter by shader referenced status
        allow_face_assign (bool): do not ignore face assignments
        filter_ (str): apply name filter

    Returns:
        (Shader, dict): shader, shading data
    """

    _LOGGER.debug('SHADING ENGINE %s', engine)
    _shd_data = {'shadingEngine': str(engine)}

    # Read shader
    _shd = engine.plug['surfaceShader'].find_incoming(plugs=False)
    if filter_ and not passes_filter(str(_shd), filter_):
        return None, None
    _LOGGER.debug(' - SHD %s %d', _shd, bool(_shd))
    if not _shd:
        _LOGGER.debug(' - NO SHADER')
        return None, None
    _shd = tex.to_shd(_shd)

    # Apply referenced filter
    if referenced is not None:
        _LOGGER.debug(' - IS REFERENCED %d', _shd.is_referenced())
        if _shd.is_referenced() != referenced:
            _LOGGER.debug(' - FILTERED')
            return None, None

    # Find geos
    try:
        _geo_ss = _shd.to_assignments()
    except RuntimeError:
        _LOGGER.error('Failed to read shader assignments %s', _shd)
        return None, None
    _LOGGER.debug(' - GEO SHPS (A) %d %s', len(_geo_ss), _geo_ss)
    _geo_ss = sorted(set(
        _geo_s for _geo_s in _geo_ss
        if not to_namespace(_geo_s) == 'lookdevRig' and  # Ignore lookdev
        not to_long(_geo_s).startswith('|JUNK|')  # Ignore junk
    ))
    _LOGGER.debug(' - GEO SHPS (B) %d %s', len(_geo_ss), _geo_ss)
    if not allow_face_assign:
        _geo_ss = [_geo_s for _geo_s in _geo_ss if '.' not in _geo_s]
        _LOGGER.debug(' - GEO SHPS (C) %d %s', len(_geo_ss), _geo_ss)
    _geos = [to_parent(_geo_s) for _geo_s in _geo_ss]
    _LOGGER.debug(' - GEOS (X) %s', _geos)
    if not _geos:
        return None, None
    _shd_data['geos'] = _geos

    # Read ai surface shader
    if engine.has_attr('aiSurfaceShader'):
        _ai_ss = engine.plug['aiSurfaceShader'].find_incoming(plugs=False)
        if _ai_ss:
            _shd_data['ai_shd'] = str(_ai_ss)

    return _shd, _shd_data
