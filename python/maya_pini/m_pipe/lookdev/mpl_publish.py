"""Tools for managing lookdev publishes."""

import copy
import collections
import logging
import re

from maya import cmds

from pini import pipe
from pini.utils import passes_filter, File

from maya_pini import open_maya as pom, tex
from maya_pini.utils import (
    to_clean, to_long, to_namespace, to_parent, save_scene)

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
    for _set, _ in read_ai_override_sets().items():
        _export_nodes.add(_set)

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


def _build_vrmesh_proxy(file_, geo, node='PXY', animation=False, force=False):
    """Build vrmesh proxy node.

    Saves out a vrmesh proxy to disk from the given geo, and then uses the
    same script to rebuild the node with shaders. This is useful because
    it's hard to script attaching the shaders to the proxy node.

    Args:
        file_ (File): vrmesh file location to save to
        geo (str list): geometry to save
        node (str): name for proxy node
        animation (bool): export animation
        force (bool): overwrite existing vrmesh file without confirmation

    Returns:
        (str): proxy node
    """

    _file = File(file_)

    _node = node
    if cmds.objExists(_node):
        _LOGGER.info(' - DELETE EXISTING PROXY NODE %s', _node)
        cmds.delete(_node)

    _file.delete(force=force)
    _file.test_dir()

    cmds.loadPlugin('vrayformaya', quiet=True)
    cmds.select(geo)
    _LOGGER.info(' - WRITE VRMESH %s', _file.path)
    _kwargs = {}
    if animation:
        _kwargs['animOn'] = True
        _kwargs['animType'] = 1  # Playback range
    else:
        _kwargs['animType'] = 0

    cmds.vrayCreateProxy(
        dir=_file.to_dir().path,
        makeBackup=True, createProxyNode=True, newProxyNode=True,
        ignoreHiddenObjects=True, oneVoxelPerMesh=True, exportHierarchy=True,
        exportType=1, facesPerVoxel=20000, fname=_file.filename,
        node=_node, pointSize=0, previewFaces=10000,
        previewType='combined', velocityIntervalEnd=0.05,
        velocityIntervalStart=0, **_kwargs)
    _LOGGER.info(' - BUILT PROXY NODE %s', _node)

    return _node


def export_vrmesh_ma(metadata, animation=False, force=False):
    """Export vrmesh maya scene.

    Saves a maya scene containing a shaded vrmesh proxy file.

    Args:
        metadata (dict): publish metadata
        animation (bool): export animation
        force (bool): overwrite existing without confirmation

    Returns:
        (CPOutput): vrmesh maya scene file
    """
    _LOGGER.info('EXPORT VRMESH MA')

    # Find export geo
    _geo = mp_utils.read_cache_set()
    _LOGGER.info(' - GEO %s', _geo)
    if not _geo:
        _LOGGER.info(' - NO GEO FOUND')
        return None

    # Setup export paths
    _vrm = pipe.cur_work().to_output(
        'publish', output_type='vrmesh', extn='vrmesh')
    _LOGGER.info(' - VRM %s', _vrm)
    _vrm_ma = pipe.cur_work().to_output(
        'publish', output_type='vrmesh', extn='ma')
    _LOGGER.info(' - MA %s', _vrm_ma)
    for _file in [_vrm, _vrm_ma]:
        _file.delete(wording='Replace', force=force)

    # Setup metadata
    _data = copy.copy(metadata)
    for _key in ['shd_yml']:
        _data.pop(_key, None)
    _data['vrmesh'] = _vrm.path

    _pxy = _build_vrmesh_proxy(
        file_=_vrm, geo=_geo, animation=animation, force=force)

    # Save proxy ma
    cmds.select(_pxy)
    assert not _vrm_ma.exists()
    save_scene(_vrm_ma, selection=True, force=force)
    cmds.delete(_pxy)
    _vrm_ma.set_metadata(_data)

    return _vrm_ma


def read_ai_override_sets(crop_namespace=True):
    """Read ai override sets.

    This is any set contained in override_SET.

    Args:
        crop_namespace (bool): remove namespace from geos

    Returns:
        (dict): set/geos
    """
    _data = {}

    if cmds.objExists('overrides_SET'):

        # Read sets to export
        _over_set = pom.CNode('overrides_SET')
        _sets = [_over_set]
        for _item in pom.CMDS.sets(_over_set, query=True):
            if _item.object_type() == 'objectSet':
                _sets.append(_item)

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
    for _shd, _data in read_shader_assignments().items():
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
            _name = _sg.attr['aiCustomAOVs[{:d}].aovName'.format(_idx)]
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

        # Read non-default settings
        for _attr in [
                'aiOpaque',
                'aiSubdivIterations',
                'aiSubdivType',
        ]:
            if not _geo.shp.has_attr(_attr):
                continue
            _plug = _geo.shp.plug[_attr]
            _def = _plug.get_default()
            _val = _plug.get_val()
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
    _data['ai_override_sets'] = read_ai_override_sets()
    _data['lights'] = _read_lights()

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
    _geo_ss = _shd.to_assignments()
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
