"""General utilities for managing pipeline references in maya."""

import logging

from maya import cmds

from pini import pipe
from pini.utils import EMPTY

_LOGGER = logging.getLogger(__name__)


def apply_grouping(top_node, output, group=EMPTY):
    """Apply organising references into groups.

    Args:
        top_node (CTransform): top node
        output (CPOutput): reference output
        group (str): group name (if any)
    """
    _LOGGER.debug('APPLY GROUPING %s group=%s', top_node, group)
    _LOGGER.debug(' - OUT %s', output)

    # Determine group to add
    _grp = group
    if output and _grp is EMPTY:
        _LOGGER.debug(' - BASIC TYPE %s', output.basic_type)
        if output.entity.name == 'camera':
            _LOGGER.debug(' - CAM ASSET')
            _grp = 'CAM'
        elif pipe.map_task(output.task) == 'lookdev':
            _LOGGER.debug(' - LOOKDEV')
            _grp = 'LOOKDEV'
        elif output.asset_type:
            _LOGGER.debug(' - USE ASSET TYPE %s', output.asset_type)
            _grp = output.asset_type.upper()
        elif output.output_type:
            _grp = output.output_type.upper()
        elif output.basic_type == 'cache':
            _grp = 'CACHE'
        else:
            _grp = None
        if _grp:
            _grp = _clean_grp(_grp)
            _LOGGER.debug(' - CLEAN GRP %s', _grp)
    _LOGGER.debug(' - GRP %s', _grp)

    # Catch grp already exists in hierarchy
    if (
            isinstance(_grp, str) and
            len(cmds.ls(_grp)) > 1 and
            not _grp.startswith('|')):
        _grp = f'|{_grp}'

    _LOGGER.debug(' - GROUP %s -> %s', group, _grp)

    if _grp:
        _LOGGER.debug(' - ADD TO GROUP %s %s', top_node, _grp)
        _grp = top_node.add_to_grp(_grp)
        _grp.solidify()


def _clean_grp(grp):
    """Clean a group name to make it a valid maya node name.

    eg. "Test Asset" -> "TestAsset"
        "260327 Frida" -> "Frida"

    Args:
        grp (str): group name

    Returns:
        (str): clean group name
    """
    _chrs = []
    for _chr in grp:
        if _chr.isdigit() or _chr.isspace():
            continue
        _chrs.append(_chr)
    return ''.join(_chrs)


def lock_cams(ref_):
    """Lock all camera channel box chans in the given reference.

    Args:
        ref_ (CReference): reference to find cameras in
    """
    _LOGGER.debug('LOCK CAMS %s', ref_)
    for _cam in ref_.find_nodes(type_='camera'):
        _LOGGER.debug(' - CAM %s', _cam)
        for _node in [_cam, _cam.shp]:
            for _plug in _node.list_attr(keyable=True):
                _plug.lock()
