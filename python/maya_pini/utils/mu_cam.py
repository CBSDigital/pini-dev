"""General maya utilities relating to cameras."""

import logging

from maya import cmds

from pini.utils import single

_LOGGER = logging.getLogger(__name__)


def find_cams(orthographic=False, default=None, renderable=None,
              referenced=None):
    """Find cameras in the current scene.

    Args:
        orthographic (bool): filter by orthographic status
        default (bool): filter by whether camera is in default nodes
        renderable (bool): filter by renderable status
        referenced (bool): filter by whether camera is referenced

    Returns:
        (str list): matching cameras
    """
    from maya_pini.utils import DEFAULT_NODES

    _cams = []
    for _cam_s in cmds.ls(type='camera'):
        _LOGGER.debug(' - CHECKING CAM %s', _cam_s)
        if orthographic is not None:
            _ortho = cmds.getAttr(_cam_s + '.orthographic')
            if orthographic != _ortho:
                _LOGGER.debug('   - ORTHO FILTER %s', _cam_s)
                continue
        if default is not None:
            _default = _cam_s in DEFAULT_NODES
            if default != _default:
                continue
        if referenced is not None:
            _refd = cmds.referenceQuery(_cam_s, isNodeReferenced=True)
            if referenced != _refd:
                continue
        if renderable is not None:
            _ren = cmds.getAttr(_cam_s + '.renderable')
            if renderable != _ren:
                _LOGGER.debug('   - REN FILTER %s', _cam_s)
                continue
        _cam = str(single(cmds.listRelatives(_cam_s, parent=True)))
        _cams.append(_cam)

    return _cams
