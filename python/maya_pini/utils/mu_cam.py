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
            _ortho = cmds.getAttr(_cam_s+'.orthographic')
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
            _ren = cmds.getAttr(_cam_s+'.renderable')
            if renderable != _ren:
                _LOGGER.debug('   - REN FILTER %s', _cam_s)
                continue
        _cam = str(single(cmds.listRelatives(_cam_s, parent=True)))
        _cams.append(_cam)

    return _cams


def find_render_cam(catch=False):
    """Find scene render camera.

    Args:
        catch (bool): no error if exactly one camera is not found

    Returns:
        (str): camera transform
    """
    from pini.tools import release
    release.apply_deprecation('11/03/24', 'Use pom.find_render_cam')

    _cams = set(find_cams())
    _LOGGER.debug("FIND RENDER CAMS %s", sorted(_cams))

    # Remove non-renderable
    if len(_cams) > 1:
        _ren = set(find_cams(renderable=True))
        if _cams & _ren:
            _cams &= _ren
            _LOGGER.debug(" - RENDERABLE %s", sorted(_cams))

    # Remove non-orthographic cams
    if len(_cams) > 1:
        _non_ortho = set(find_cams(orthographic=False))
        if _cams & _non_ortho:
            _cams &= _non_ortho
            _LOGGER.debug(" - NON ORTHO %s", sorted(_cams))

    # Remove default cams
    if len(_cams) > 1:
        _non_default = set(find_cams(default=False))
        if _cams & _non_default:
            _cams &= _non_default
            _LOGGER.debug(' - NON DEFAULT %s', sorted(_cams))

    # Remove referenced cams
    if len(_cams) > 1:
        _non_refd = set(find_cams(referenced=False))
        if _cams & _non_refd:
            _cams &= _non_refd
            _LOGGER.debug(' - NON REFERENCED %s', sorted(_cams))

    return single(_cams, catch=catch)
