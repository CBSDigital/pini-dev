"""Vray lookdev tools.

This page has docs about adding vray attributes
https://github.com/BigRoy/mayaVrayCommandDocs/wiki/vray-addAttributesFromGroup
"""

import copy
import logging

from maya import cmds

from pini import pipe
from pini.utils import File, cache_result

from maya_pini import open_maya as pom
from maya_pini.utils import save_scene, restore_sel

from .. import mp_utils

_LOGGER = logging.getLogger(__name__)


def check_vray_mesh_setting(mesh, attr):
    """Check for a vray mesh setting, creating it if needed.

    If the setting is missing then it is created using the vray callback.

    Args:
        mesh (str): name of mesh to check (shape node)
        attr (str): attibute to check
    """
    _mesh = pom.CNode(mesh)
    if _mesh.has_attr(attr):
        return
    assert attr.startswith('vray')
    cmds.loadPlugin('vrayformaya', quiet=True)
    _type = _read_vray_type_map()[attr]
    cmds.vray("addAttributesFromGroup", _mesh, _type, 1)
    assert _mesh.has_attr(attr)


@cache_result
@restore_sel
def _read_vray_type_map():
    """Read vray setting type mapping.

    Vray settings are grouped into types with each type containing
    a number of settings. To create a setting, you need to know which
    type it falls under.

    To read the types, a tmp mesh is created, and then each type is
    applied to this mesh to find which attributes it creates. This is
    intended to be more robust than hardcoding the mapping. There is
    a link to some vray settings documentation in the module docstring.

    Returns:
        (dict): attibute/type mapping
    """
    _tmp = pom.CMDS.polyCube()
    _map = {}
    for _type in [
            'vray_subdivision',
            'vray_subquality',
            'vray_displacement',
            'vray_roundedges',
            'vray_user_attributes',
            'vray_objectID',
            'vray_fogFadeOut',
            'vray_phoenix_object',
    ]:
        _pre_plugs = _tmp.shp.list_attr(user_defined=True)
        cmds.vray("addAttributesFromGroup", _tmp.shp, _type, 1)
        _post_plugs = _tmp.shp.list_attr(user_defined=True)
        _new_plugs = sorted(set(_post_plugs) - set(_pre_plugs))
        _LOGGER.debug(' - TYPE %s %d %s', _type, len(_new_plugs), _new_plugs)
        for _plug in _new_plugs:
            _map[_plug.attr] = _type
    _tmp.delete()
    return _map


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
        _file.delete(wording='replace', force=force)

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
