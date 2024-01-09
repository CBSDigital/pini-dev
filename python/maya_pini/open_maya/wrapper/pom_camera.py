"""Tools for adding functionilty to OpenMaya.MFnCamera object."""

import logging

from maya import cmds
from maya.api import OpenMaya as om

from pini.utils import single, passes_filter
from maya_pini import ui
from maya_pini.utils import to_shp, DEFAULT_NODES, to_node

from .. import base
from ..pom_utils import to_mobject

_LOGGER = logging.getLogger(__name__)


class CCamera(base.CBaseTransform, om.MFnCamera):
    """Wrapper for OpenMaya.MFnCamera object."""

    def __init__(self, node, shp=None):
        """Constructor.

        Args:
            node (str): camera transform (eg. persp)
            shp (str): camera shape node if known
        """
        _node = node
        if isinstance(_node, base.CBaseNode):
            _node = str(node)
        super(CCamera, self).__init__(_node)

        _shp = shp or to_shp(_node, type_='camera')
        _m_obj = to_mobject(_shp)
        om.MFnCamera.__init__(self, _m_obj)

    def to_shp(self, type_=None, catch=False):
        """Get this camera's shape node.

        Args:
            type_ (str): filter by shape type (default is camera)
            catch (bool): no error if not shape found

        Returns:
            (CNode): camera shape
        """
        _shps = self.to_shps(type_=type_ or 'camera')
        return single(_shps, catch=catch)

    @property
    def renderable(self):
        """Obtain renderable plug of shape node.

        Returns:
            (CPlug): shape renderable
        """
        return self.shp.plug['renderable']

    def is_orthographic(self):
        """Check if this camera is orthographic.

        Returns:
            (bool): whether orthographic
        """
        return self.shp.plug['orthographic'].get_val()


def active_cam():
    """Get active viewport camera.

    Returns:
        (CCamera): active camera
    """
    _name = ui.get_active_cam()
    if not _name:
        return None
    _clean_name = to_node(_name)
    _LOGGER.debug('ACTIVE CAM %s clean=%s', _name, _clean_name)
    if _name != _clean_name and single(cmds.ls(_clean_name), catch=True):
        _LOGGER.debug(' - CLEAN NAME IS SAFE')
        _name = _clean_name
    return CCamera(_name)


def find_cam(default=False, orthographic=False, filter_=None):
    """Find matching camera in this scene.

    Args:
        default (bool): include default cameras
        orthographic (bool): include orthographic cameras
        filter_ (str): apply name filter

    Returns:
        (CCamera): camera
    """
    _cams = find_cams(
        default=default, orthographic=orthographic, filter_=filter_)
    return single(_cams)


def find_cams(
        default=None, referenced=None, renderable=None, orthographic=False,
        filter_=None):
    """Find cameras in the current scene.

    Args:
        default (bool): include default cameras
        referenced (bool): filter by camera referenced state
        renderable (bool): filter by renderable state
        orthographic (bool): filter by orthographic state
        filter_ (str): apply name filter

    Returns:
        (CCamera list): cameras
    """
    from maya_pini import open_maya as pom
    _cams = []
    for _cam in pom.find_nodes(type_='camera'):
        if filter_ and not passes_filter(str(_cam), filter_):
            continue
        if default is not None and str(_cam) in DEFAULT_NODES:
            continue
        if referenced is not None and _cam.is_referenced() != referenced:
            continue
        if orthographic is not None and _cam.is_orthographic() != orthographic:
            continue
        if renderable is not None and _cam.renderable.get_val() != renderable:
            continue
        _cams.append(_cam)
    return _cams


def find_render_cam():
    """Find current scene render cam.

    Returns:
        (CCamera): renderable camera (if any)
    """
    _cams = find_cams(default=None, renderable=True)
    if len(_cams) == 1:
        return single(_cams)
    _cams = find_cams(default=False, renderable=True)
    if len(_cams) == 1:
        return single(_cams)
    raise ValueError('Failed to find render camera')


def set_render_cam(camera):
    """Set renderable camera (and set other cameras to unrenderable).

    Args:
        camera (CCamera): camera to set as renderable
    """
    _cam = CCamera(camera)
    _LOGGER.debug('SET CAM RENDERABLE %s', _cam)
    for _o_cam in find_cams(default=None):
        if _o_cam == _cam:
            continue
        _LOGGER.debug(' - APPLY %s %d', _o_cam.renderable, False)
        _o_cam.renderable.set_val(False)
    _cam.renderable.set_val(True)
