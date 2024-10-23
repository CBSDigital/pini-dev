"""Top level tools for managing maya pipe refs."""

import logging

from pini.utils import passes_filter

from . import prm_ref, prm_node

_LOGGER = logging.getLogger(__name__)


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
    _refs += prm_ref.read_reference_pipe_refs(selected=selected)

    _refs += prm_node.read_aistandins(selected=selected)
    _refs += prm_node.read_img_planes(selected=selected)
    _refs += prm_node.read_rs_pxys(selected=selected)
    _refs += prm_node.read_vdbs(selected=selected)

    if extn:
        _refs = [_ref for _ref in _refs if _ref.extn == extn]
    if filter_:
        _refs = [_ref for _ref in _refs
                 if passes_filter(_ref.namespace, filter_)]

    return _refs
