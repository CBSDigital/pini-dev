"""Tools for managing abcs in houdini."""

import logging

import hou

from pini import dcc
from pini.utils import File

_LOGGER = logging.getLogger(__name__)


def import_abc(abc, namespace, mode='archive'):
    """Import abc into current scene.

    Args:
        abc (File): abc file to import
        namespace (str): namespace for abc
        mode (str): import mode (archive/geometry)
            - archive supports cameras

    Returns:
        (CPipeRef): abc reference
    """
    _mode = mode

    if _mode == 'geometry':
        _ref = import_abc_geometry(abc, namespace)
    elif _mode == 'archive':
        _ref = import_abc_archive(abc, namespace)
    else:
        raise ValueError(mode)

    return _ref


def import_abc_archive(abc, namespace):
    """Import abc using archive node.

    Args:
        abc (File): abc file to import
        namespace (str): namespace for abc

    Returns:
        (CPipeRef): abc reference
    """
    _file = File(abc)
    _LOGGER.debug('IMPORT ABC CAM %s', _file.path)

    _root = hou.node('/obj')

    _archive = _root.createNode('alembicarchive', namespace)
    _archive.parm('fileName').set(_file.path)
    _archive.parm('buildHierarchy').pressButton()

    _input_1 = _archive.item('1')
    _abcs = _input_1.outputs()

    # Apply scale
    _null = _archive.createNode('null', 'scale')
    _null.setInput(0, _input_1)
    _null.setPosition(_input_1.position() + hou.Vector2(0, -1))
    _null.parm('scale').set(0.01)
    for _abc in _abcs:
        _abc.setInput(0, _null)

    _ref = dcc.find_pipe_ref(namespace)
    _ref.update_res()

    return _ref


def import_abc_geometry(abc, namespace):
    """Import abc using alembic geometry node.

    Args:
        abc (File): abc file to import
        namespace (str): namespace for abc

    Returns:
        (CPipeRef): abc reference
    """

    _file = File(abc)
    _LOGGER.debug('IMPORT ABC GEO %s', _file.path)

    _root = hou.node('/obj')
    _geo = _root.createNode('geo', node_name=namespace)

    _abc = _geo.createNode('alembic')
    _abc.parm('fileName').set(_file.path)

    _tfm = _geo.createNode('xform', 'scale')
    _tfm.setInput(0, _abc)
    _tfm.parm('scale').set(0.01)
    _tfm.setPosition((0, -1))

    _out = _geo.createNode('null', 'OUT')
    _out.setInput(0, _tfm)
    _out.setRenderFlag(True)
    _out.setDisplayFlag(True)
    _out.setPosition((0, -2))

    return dcc.find_pipe_ref(namespace)
