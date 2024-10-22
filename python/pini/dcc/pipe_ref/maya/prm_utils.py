"""General utilities for managing pipeline references in maya."""

import logging

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
    _LOGGER.debug(' - OUT %s', output)

    # Determine group to add
    _grp = group
    if output and _grp is EMPTY:
        if output.entity.name == 'camera':
            _grp = 'CAM'
        elif pipe.map_task(output.task) == 'LOOKDEV':
            _grp = 'LOOKDEV'
        elif output.asset_type:
            _grp = output.asset_type.upper()
        elif output.output_type:
            _grp = output.output_type.upper()
        elif output.basic_type == 'cache':
            _grp = 'CACHE'
        else:
            _grp = None
    _LOGGER.debug(' - GROUP %s -> %s', group, _grp)

    if _grp:
        _LOGGER.debug(' - ADD TO GROUP %s %s', top_node, _grp)
        _grp = top_node.add_to_grp(_grp)
        _grp.solidify()


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
