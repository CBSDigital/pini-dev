"""Top level tools for managing maya pipe refs."""

import logging

from pini import pipe, dcc
from pini.utils import passes_filter

from . import prm_ref, prm_node

_LOGGER = logging.getLogger(__name__)


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


def find_pipe_refs(filter_=None, selected=False, extn=None):
    """Find pipelined references in the current scene.

    Args:
        filter_ (str): filter list by namespace
        selected (bool): only find selected refs
        extn (str): filter by reference extension

    Returns:
        (CMayaPipeRef list): pipelined references
    """
    _refs = []
    _refs += prm_ref.find_reference_pipe_refs(selected=selected)

    _refs += prm_node.find_ai_standins(selected=selected)
    _refs += prm_node.find_ai_vols(selected=selected)
    _refs += prm_node.find_img_planes(selected=selected)
    _refs += prm_node.find_rs_dome_lights(selected=selected)
    _refs += prm_node.find_rs_pxys(selected=selected)
    _refs += prm_node.find_rs_volumes(selected=selected)

    if extn:
        _refs = [_ref for _ref in _refs if _ref.extn == extn]
    if filter_:
        _refs = [_ref for _ref in _refs
                 if passes_filter(_ref.namespace, filter_)]

    return _refs
