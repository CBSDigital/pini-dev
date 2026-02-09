"""Top level tools for managing maya pipe refs."""

import logging

from pini import pipe, dcc
from pini.utils import passes_filter, EMPTY, Path, abs_path

from maya_pini import open_maya as pom

from . import prm_ref, prm_node, prm_utils

_LOGGER = logging.getLogger(__name__)


def create_ref(path, namespace, group=EMPTY, parent=None, force=False):
    """Create reference instance of the given path.

    Args:
        path (File): file to reference
        namespace (str): namespace reference
        group (str): override group (otherwise references are automatically
            put in a group based on the asset/output type)
        parent (QDialog): parent dialog for any popups
        force (bool): replace existing without confirmation

    Returns:
        (CMayaPipeRef): reference
    """
    _LOGGER.debug('CREATE REF %s', namespace)

    # Check path/output
    _path = path
    if isinstance(_path, str):
        _path = Path(abs_path(_path))
    _LOGGER.debug(' - PATH %s', path)
    _out = pipe.CACHE.obt_output(_path, catch=True)
    _LOGGER.debug(' - OUT %s %s', _out, _out.content_type if _out else '')

    # Bring in reference
    if _out and _out.content_type == 'CurvesMb':
        _ref = create_curves_mb_ref(
            path, namespace=namespace, group=group, parent=parent, force=force)
    elif _path.extn == 'vdb':
        _ref = prm_node.create_ai_vol(
            _path, namespace=namespace, group=group)
    elif _path.extn in ('ass', 'usd', 'gz'):
        _ref = prm_node.create_ai_standin(
            path=_path, namespace=namespace, group=group)
    elif _path.extn in ('rs', ):
        _ref = prm_node.create_rs_pxy(
            _path, namespace=namespace, group=group)
    else:
        _pom_ref = pom.create_ref(
            _path, namespace=namespace, parent=parent, force=force)
        _ns = _pom_ref.namespace
        _ref = dcc.find_pipe_ref(_ns, catch=True)
        if not _ref:
            raise RuntimeError(f'Failed to find ref {_ns}')
        if _ref.top_node:
            prm_utils.apply_grouping(
                top_node=_ref.top_node, output=_ref.output, group=group)
        prm_utils.lock_cams(_pom_ref)

    _LOGGER.debug(' - REF %s', _ref)

    return _ref


def create_cam_ref(cam, build_plates=True, namespace=None, force=False):
    """Create camera reference.

    Args:
        cam (CPOutput): output to reference
        build_plates (bool): build plates using metadata
        namespace (str): reference namespace
        force (bool): replace existing without confirmation

    Returns:
        (CMayaRef): reference
    """
    _cam = pipe.CACHE.obt(cam)
    assert _cam.extn in ('abc', 'fbx')

    _LOGGER.debug('CREATE CAM REF')

    _ns = namespace
    if not namespace:
        raise NotImplementedError

    _ref = dcc.create_ref(_cam, namespace=_ns, force=force)
    _LOGGER.debug(' - REF %s', _ref)
    if build_plates:
        _ref.build_plates()

    return _ref


def create_curves_mb_ref(  # pylint: disable=unused-argument
        output, namespace, group=EMPTY, parent=None, force=False):
    """Create reference instance of the given curves mb file.

    Args:
        output (CPOutput): curves mb output
        namespace (str): namespace reference
        group (str): override group (otherwise references are automatically
            put in a group based on the asset/output type)
        parent (QDialog): parent dialog for any popups
        force (bool): replace existing without confirmation

    Returns:
        (CMayaPipeRef): reference
    """

    import pprint
    pprint.pprint(output.metadata)
    raise NotImplementedError


def find_pipe_refs(filter_=None, selected=False, extn=None):
    """Find pipelined references in the current scene.

    Args:
        filter_ (str): filter list by namespace
        selected (bool): only find selected refs
        extn (str): filter by reference extension

    Returns:
        (CMayaPipeRef list): pipelined references
    """
    _LOGGER.debug('FIND PIPE REFS')

    _refs = []
    _refs += prm_ref.find_reference_pipe_refs(selected=selected)
    _LOGGER.debug(' - ADDED REFERENCES %d', len(_refs))

    _refs += prm_node.find_ai_standins(selected=selected)
    _LOGGER.debug(' - ADDED AI STANDINS %d', len(_refs))
    _refs += prm_node.find_ai_vols(selected=selected)
    _LOGGER.debug(' - ADDED AI VOLS %d', len(_refs))
    _refs += prm_node.find_file_nodes(selected=selected)
    _LOGGER.debug(' - ADDED FILE NODES %d', len(_refs))
    _refs += prm_node.find_img_planes(selected=selected)
    _LOGGER.debug(' - ADDED IMG PLANES %d', len(_refs))
    _refs += prm_node.find_rs_dome_lights(selected=selected)
    _refs += prm_node.find_rs_pxys(selected=selected)
    _refs += prm_node.find_rs_volumes(selected=selected)

    if extn:
        _refs = [_ref for _ref in _refs if _ref.extn == extn]
    if filter_:
        _refs = [_ref for _ref in _refs
                 if passes_filter(_ref.namespace, filter_)]

    return _refs
