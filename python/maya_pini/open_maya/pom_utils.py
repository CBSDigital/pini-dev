"""General utilities for pom."""

import logging

import six

from maya import cmds
from maya.api import OpenMaya as om

from pini.utils import single, EMPTY, passes_filter
from maya_pini.utils import to_parent, to_shp, restore_sel

_LOGGER = logging.getLogger(__name__)


@restore_sel
def add_anim_offs(tfm, anim):
    """Build animation offset controls.

    Args:
        tfm (CTransform): node to apply offset controls on
        anim (CAnimCurve list): animation to offset
    """
    from maya_pini import open_maya as pom

    # Create attrs
    _mult = tfm.add_attr('animMult', 1.0)
    _offs = tfm.add_attr('animOffset', 0.0)
    _anim_t = tfm.add_attr('animTime', 0.0)

    # Connect nodes
    _offs_t = pom.minus_plug('time1.outTime', _offs)
    _offs_t.multiply(_mult, output=_anim_t, force=True)
    _LOGGER.info(' - MULT/OFFS %s %s', _mult, _offs)
    for _crv in anim:
        _anim_t.connect(_crv.input, force=True, break_connections=True)


def cast_node(node, type_=None, class_=None, maintain_shapes=False):
    """Cast a node to an appropriate pom type.

    Args:
        node (str): node to cast
        type_ (str): node type (if known)
        class_ (class): force result class
        maintain_shapes (bool): don't update a shape node to its parent
            node type (eg. return camera as CNode not CCamera)

    Returns:
        (CNode|CTransform|CCamera): node object
    """
    from maya_pini import open_maya as pom

    _LOGGER.debug('CAST NODE %s type=%s', node, type_)
    _node = node

    # Determine type
    assert isinstance(_node, six.string_types)
    _type = type_ or cmds.objectType(node)
    _LOGGER.debug(' - TYPE %s', _type)

    # Choose node class
    _kwargs = {}
    if class_:
        _class = class_
    elif not maintain_shapes and _type == 'camera':
        _class = pom.CCamera
        _shp = _node
        _node = to_parent(_shp)
        _kwargs['shp'] = _shp
    elif _type == 'joint':
        _class = pom.CJoint
    elif _type == 'mesh':
        _class = pom.CMesh
        _shp = _node
        _node = to_parent(_shp)
    elif _type == 'transform':
        _class = _cast_tfm(_node)
    elif _type.startswith('animCurve'):
        _class = pom.CAnimCurve
    else:
        _class = pom.CNode

    _LOGGER.debug(' - CLASS %s', _class)
    _result = _class(_node, **_kwargs)
    _LOGGER.debug(' - RESULT %s type=%s', _result, type(_result))
    return _result


def _cast_tfm(node):
    """Cast a transform node based on its shape.

    Args:
        node (str): transform node to cast

    Returns:
        (class): target node class
    """
    from maya_pini import open_maya as pom

    _shp = to_shp(node, catch=True)
    _LOGGER.debug(' - SHP %s', _shp)
    if not _shp:
        return pom.CTransform

    _shp_type = cmds.objectType(_shp)
    _LOGGER.debug(' - SHP TYPE %s', _shp_type)
    if _shp_type == 'mesh':
        _class = pom.CMesh
    elif _shp_type == 'camera':
        _class = pom.CCamera
    elif _shp_type == 'nurbsCurve':
        _class = pom.CNurbsCurve
    else:
        _class = pom.CTransform
    return _class


def find_connections(
        obj, source=True, destination=True, type_=None, connections=True,
        plugs=True):
    """Find connections on the given plug or node.

    Args:
        obj (CNode|CPlug): object to read connections on
        source (bool): include source connections
        destination (bool): include destination connections
        type_ (str): filter by node type
        connections (bool): return src/dest pairs rathen than just the
            opposite end of the connection
        plugs (bool): return plugs rather than nodes

    Returns:
        (CPlug tuple list): connection plug pairs (by default)
    """
    from maya_pini import open_maya as pom

    _LOGGER.debug('FIND CONNECTIONS %s connections=%d plugs=%d', obj,
                  connections, plugs)

    _flags = []
    if source:
        _flags.append((True, False))
    if destination:
        _flags.append((False, True))

    # Obtain and sort results
    _results = []
    for _src, _dest in _flags:

        # Read connections
        _kwargs = {}
        if type_:
            _kwargs['type'] = type_
        _conns = cmds.listConnections(
            obj, plugs=plugs, connections=True, source=_src,
            destination=_dest, **_kwargs)
        _conns = _conns or []
        if plugs:
            _conns = [pom.CPlug(_conn) for _conn in _conns]
        else:
            _conns = [pom.to_node(_conn) for _conn in _conns]
        _LOGGER.debug(' - %s %s %s', 'SRC' if _src else 'DST',
                      (_src, _dest), _conns)

        # Sort results into pairs
        assert not len(_conns) % 2  # Check even number of results
        if _src:  # Process incoming
            _conns = [(_conns[2*_idx+1], _conns[2*_idx])
                      for _idx in range(int(len(_conns)/2))]
            _LOGGER.debug(' - SORTED INCOMING %s', _conns)
            if not connections:
                _conns = [_src for _src, _ in _conns]
                _LOGGER.debug(' - CLEANED INCOMING %s', _conns)
        else:  # Process outgoing
            _conns = [(_conns[2*_idx], _conns[2*_idx+1])
                      for _idx in range(int(len(_conns)/2))]
            _LOGGER.debug(' - SORTED OUTGOING %s', _conns)
            if not connections:
                _conns = [_dest for _, _dest in _conns]
                _LOGGER.debug(' - CLEANED OUTGOING %s', _conns)

        _results += _conns

    _LOGGER.debug(' - RESULTS %s', _results)

    return _results


def find_nodes(
        type_=None, namespace=EMPTY, referenced=None, filter_=None,
        clean_name=None):
    """Find nodes in the current scene.

    Args:
        type_ (str): filter by node type
        namespace (str): filter by namespace
        referenced (bool): filter by node referenced status
        filter_ (str): node name filter
        clean_name (str): filter by clean name

    Returns:
        (CBaseNode list): nodes in scene
    """
    from maya_pini import open_maya as pom

    # Read outputs
    _kwargs = {}
    if type_:
        _kwargs['type'] = type_
    _results = pom.CMDS.ls(**_kwargs)

    _nodes = []
    for _node in _results:
        if filter_ and not passes_filter(str(_node), filter_):
            continue
        if namespace is not EMPTY and _node.namespace != namespace:
            continue
        if referenced is not None and _node.is_referenced() != referenced:
            continue
        if clean_name and _node.clean_name != clean_name:
            continue
        _nodes.append(_node)
    return _nodes


def get_selected(class_=None, multi=False):
    """Obtain selected pom node.

    Args:
        class_ (class): cast result to this class
        multi (bool): allow multiple selection

    Returns:
        (CNode): selected node
    """
    _LOGGER.debug('GET SELECTED')
    assert isinstance(multi, bool)
    _sel = cmds.ls(selection=True)
    if multi:
        return [cast_node(_item, class_=class_) for _item in _sel]
    _node = single(_sel, error='{:d} items selected'.format(len(_sel)))
    return cast_node(_node, class_=class_)


def set_loc_scale(scale):
    """Set default locator scale.

    Args:
        scale (float): scale to apply
    """
    from maya_pini import open_maya as pom
    pom.LOC_SCALE = scale


def _read_child_geos(obj):
    """Read geometry children of the given object.

    Args:
        obj (CTransform): root object

    Returns:
        (CMesh list): child meshes
    """
    from maya_pini import open_maya as pom

    _obj = obj
    _type = obj.object_type()
    _shp = to_shp(str(_obj), catch=True)

    _geos = []
    if _type == 'transform':

        _tfm = None
        if _shp:
            _shp = pom.CNode(_shp)
            _shp_type = _shp.object_type()
            if _shp_type == 'mesh':
                _tfm = pom.CMesh(str(_obj))
                _geos.append(_tfm)
        if not _tfm:
            _tfm = pom.CTransform(_obj)

        for _child in _tfm.find_children():
            _geos += _read_child_geos(_child)

    return _geos


def set_to_geos(set_):
    """Get a list of meshes in the given set.

    Args:
        set_ (CNode): object set to read

    Returns:
        (CMesh list): meshes
    """
    from maya_pini import open_maya as pom
    _geos = []
    for _item in pom.CMDS.sets(set_, query=True):
        _geos += _read_child_geos(_item)
    return _geos


def _read_child_tfms(obj):
    """Read child transforms of the given object.

    Args:
        obj (CTransform): object to read

    Returns:
        (CTransform list): child transforms
    """
    from maya_pini import open_maya as pom
    _obj = obj
    _type = obj.object_type()
    _tfms = []
    if _type == 'transform':
        _tfm = pom.CTransform(_obj)
        _tfms.append(_tfm)
        for _child in _tfm.find_children():
            _tfms += _read_child_geos(_child)
    return _tfms


def set_to_tfms(set_):
    """Obtain list of transforms in the given set.

    Args:
        set_ (CNode): set to read

    Returns:
        (CTransform list): transforms
    """
    from maya_pini import open_maya as pom
    _tfms = []
    for _item in pom.CMDS.sets(set_, query=True):
        _tfms += _read_child_tfms(_item)
    return _tfms


def to_mesh(node):
    """Obtain a mesh object from the given data.

    Args:
        node (str|CMesh): object to map to a mesh

    Returns:
        (CMesh): matching mesh
    """
    from maya_pini import open_maya as pom
    if isinstance(node, six.string_types):
        return pom.CMesh(node)
    if isinstance(node, pom.CMesh):
        return node
    return ValueError(node)


def to_mobject(node):
    """Build MObject for the given node.

    Args:
        node (str): node to convert

    Returns:
        (MObject): open maya object
    """
    from maya_pini import open_maya as pom
    _LOGGER.debug('TO MOBJECT %s', node)

    # Obtain node as str
    _node = node
    if isinstance(_node, pom.CBaseNode):
        _node = str(_node)
    if not isinstance(_node, six.string_types):
        raise NotImplementedError(_node)

    # Build tmp selection list
    _tmp = om.MSelectionList()
    try:
        _tmp.add(_node)
    except RuntimeError as _exc:
        _LOGGER.debug(' - EXC %s', _exc)
        if str(_exc).endswith('Object does not exist'):
            raise RuntimeError('Missing node {}'.format(node))
        raise _exc
    _obj = _tmp.getDependNode(0)
    return _obj


def to_mdagpath(node):
    """Build an MDagPath object for the given node.

    Args:
        node (MDagPath): node to convert

    Returns:
        (MDagPath): open maya dag path
    """
    try:
        _sel = om.MGlobal.getSelectionListByName(node)
    except RuntimeError as _exc:
        if not cmds.objExists(node):
            raise RuntimeError('Missing node '+node)
        raise _exc
    return _sel.getDagPath(0)


def _local_axes_to_m(pos, lx, ly, lz=None):
    """Build a matrix from the given position and local axes.

    Args:
        pos (CPoint): position
        lx (CVector): local x
        ly (CVector): local y
        lz (CVector): local z

    Returns:
        (CMatrix): transformation matrix
    """
    from maya_pini import open_maya as pom
    _lz = lz
    if not _lz:
        _lz = (lx ^ ly).normalize()
    return pom.CMatrix([
        lx[0],    lx[1],   lx[2],  0,
        ly[0],    ly[1],   ly[2],  0,
        _lz[0],  _lz[1],  _lz[2],  0,
        pos[0],  pos[1],  pos[2],  1])


def selected_node():
    """Obtain currently selected node.

    Returns:
        (CNode): selected node
    """
    return cast_node(single(cmds.ls(selection=True)))


def to_m(*args, **kwargs):
    """Obtain a matrix from the given data.

    eg. to_m('persp') -> CMatrix  # persp matrix
        to_m(pos, lx, ly, lz) -> CMatrix  # matrix from local axes

    Returns:
        (CMatrix): matrix
    """
    if len(args) == 1:
        _tfm = to_tfm(single(args))
        return _tfm.to_m()

    if 'pos' in kwargs and len(kwargs) in (3, 4):
        return _local_axes_to_m(**kwargs)

    raise ValueError


def to_node(obj):
    """Build a node object from the given name.

    eg. pom.to_node('persp') -> pom.CNode('persp')

    Args:
        obj (str): name to build node from

    Returns:
        (CNode): node
    """
    from maya_pini import open_maya as pom
    from maya_pini.utils import to_node as _to_node

    if isinstance(obj, pom.CBaseNode):
        return obj
    if isinstance(obj, six.string_types):
        return pom.CNode(_to_node(obj))
    if isinstance(obj, pom.CPlug):
        return obj.node
    raise ValueError(obj)


def to_p(*args):
    """Obtain position  object from the given args.

    eg. to_p('persp') -> CPoint
        to_p(1, 2, 3) -> CPoint

    Returns:
        (CPoint): position
    """
    from maya_pini import open_maya as pom

    if len(args) == 1 and isinstance(args[0], (
                six.string_types,
                pom.CBaseNode)):
        _obj = single(args)
        _val = cmds.xform(_obj, query=True, worldSpace=True, translation=True)
        return pom.CPoint(_val)

    if len(args) == 3:
        return pom.CPoint(*args)

    raise ValueError(args)


def to_tfm(obj):
    """Obtain a transform from the given object.

    Args:
        obj (str|CTransform|CNode): object to read

    Returns:
        (CTransform): transform node
    """
    from maya_pini import open_maya as pom
    if isinstance(obj, pom.CTransform):
        return obj
    _node = to_node(obj)
    return pom.CTransform(_node)
