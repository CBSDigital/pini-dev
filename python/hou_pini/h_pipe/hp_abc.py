"""Tools for managing abcs in houdini."""

import logging

import hou

from pini import dcc, install
from pini.utils import File, single

_LOGGER = logging.getLogger(__name__)


def import_abc(abc, namespace, mode='archive', apply_scale_fix=None):
    """Import abc into current scene.

    Args:
        abc (File): abc file to import
        namespace (str): namespace for abc
        mode (str): import mode (archive/geometry)
            - archive supports cameras
        apply_scale_fix (bool): apply 0.01 scale fix

    Returns:
        (CPipeRef): abc reference
    """

    # Read scale fix env if undeclared
    _apply_scale_fix = apply_scale_fix
    if _apply_scale_fix is None:
        _apply_scale_fix = install.read_env(
            'PINI_HOU_APPLY_SCALE_FIX', default=True)

    if mode == 'geometry':
        return import_abc_geometry(
            abc, namespace, apply_scale_fix=_apply_scale_fix)
    if mode == 'archive':
        return import_abc_archive(
            abc, namespace, apply_scale_fix=_apply_scale_fix)
    raise ValueError(mode)


def import_abc_archive(abc, namespace, apply_scale_fix=True):
    """Import abc using archive node.

    Args:
        abc (File): abc file to import
        namespace (str): namespace for abc
        apply_scale_fix (bool): apply 0.01 scale fix

    Returns:
        (CPipeRef): abc reference
    """
    _LOGGER.debug('IMPORT ABC ARCHIVE %s', abc)
    _LOGGER.debug(' - NAMESPACE %s', namespace)
    _file = File(abc)
    _LOGGER.debug(' - FILE %s', _file.path)

    _root = hou.node('/obj')

    _archive = _root.createNode('alembicarchive', namespace)
    _archive.parm('fileName').set(_file.path)
    _archive.parm('buildSingleGeoNode').set(True)
    _archive.parm('buildHierarchy').pressButton()

    _input_1 = _archive.item('1')
    _geos = _input_1.outputs()
    _LOGGER.debug(' - GEOS %s', _geos)

    # Apply 0.01 scale fix
    if apply_scale_fix:
        _null = _archive.createNode('null', 'scale')
        _null.setInput(0, _input_1)
        _null.setPosition(_input_1.position() + hou.Vector2(0, -1))
        _null.parm('scale').set(0.01)
        for _geo in _geos:
            _LOGGER.debug(' - GEO %s', _geo)
            _geo.setInput(0, _null)

            _abc = single([
                _node for _node in _geo.children()
                if _node.type().name() == 'alembic'], catch=True)
            _LOGGER.debug('   - ABC %s', _abc)
            if _abc:
                _abc.parm('addpath').set(True)

    _ref = dcc.find_pipe_ref(namespace)
    _LOGGER.debug(' - CONTENT TYPE %s', _ref.output.content_type)
    if _ref.output.content_type == 'CameraAbc':
        _ref.update_camera_res()

    _archive.layoutChildren()

    return _ref


def import_abc_geometry(abc, namespace, apply_scale_fix=True):
    """Import abc using alembic geometry node.

    Args:
        abc (File): abc file to import
        namespace (str): namespace for abc
        apply_scale_fix (bool): apply 0.01 scale fix

    Returns:
        (CPipeRef): abc reference
    """
    _file = File(abc)
    _LOGGER.debug('IMPORT ABC GEO %s', _file.path)
    _LOGGER.debug(' - NAMESPACE %s', namespace)

    # Create group
    _root = hou.node('/obj')
    _geo = _root.createNode('geo', node_name=namespace)

    # Import abs
    _abc = _geo.createNode('alembic')
    _abc.parm('fileName').set(_file.path)
    _tail = _abc

    # Apply 0.01 scale fix
    if apply_scale_fix:
        _LOGGER.debug(' - APPLY SCALE FIX')
        _tfm = _geo.createNode('xform', 'scale')
        _tfm.setInput(0, _abc)
        _tfm.parm('scale').set(0.01)
        _tfm.setPosition((0, -1))
        _tail = _tfm

    # Build output null
    _out = _geo.createNode('null', 'OUT')
    _out.setInput(0, _tail)
    _out.setRenderFlag(True)
    _out.setDisplayFlag(True)
    _out.setPosition((0, -2))

    return dcc.find_pipe_ref(namespace)
