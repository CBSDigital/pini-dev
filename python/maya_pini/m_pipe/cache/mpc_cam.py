"""Tools for managing caching of cameras."""

import logging
import re

from maya import cmds

from pini import icons, dcc
from pini.utils import single

from maya_pini import ref, open_maya as pom
from maya_pini.utils import (
    DEFAULT_NODES, set_namespace, del_namespace, to_parent, set_col,
    to_clean, to_namespace)

from . import mpc_cacheable

_LOGGER = logging.getLogger(__name__)


class CPCacheableCam(mpc_cacheable.CPCacheable):  # pylint: disable=too-many-instance-attributes
    """Represents a camera that can be cached in the current scene."""

    ref = None
    cam_attrs = (
        'focalLength', 'focusDistance',
        'filmTranslateH', 'filmTranslateV')
    attrs = cam_attrs

    def __init__(self, cam):
        """Constructor.

        Args:
            cam (str): camera transform
        """
        self.cam = cam
        self.node = cam
        if cmds.referenceQuery(self.cam, isNodeReferenced=True):
            _ns = to_namespace(self.cam)
            self.ref = ref.find_ref(_ns)
            if not self.ref:  # Could be nested in which case ignore
                raise ValueError('Failed to find reference {}'.format(self.cam))
            self.output_name = self.ref.namespace
        else:
            self.output_name = to_clean(self.cam)
        self.label = self.output_name
        self.output_type = 'cam'

        self._tmp_ns = ':tmp_{}'.format(self.output_name)
        self._tmp_cam = '{}:CAM'.format(self._tmp_ns)
        self._img_plane_data = {}

    def obtain_metadata(self):
        """Obtain metadata dict for this cacheable.

        Returns:
            (dict): metadata
        """
        _data = super(CPCacheableCam, self).obtain_metadata()
        _data['res'] = dcc.get_res()
        _data['img_plane'] = self._img_plane_data
        return _data

    def _build_tmp_cam(self, scale=1.0):
        """Rename camera to tmp node name.

        This applies the name CAM in a tmp namespace to allow the top
        node of the abc to have a uniform name.

        eg. renderCam +=> tmp_renderCam:CAM

        Args:
            scale (float): override scale (for debugging - arnold can
                bug out if camera scale is not 1)
        """
        _LOGGER.info('BUILD TMP CAM %s', self)
        set_namespace(self._tmp_ns, clean=True)
        _dup = cmds.duplicate(self.cam, name='CAM')[0]
        if to_clean(_dup) != 'CAM':
            _dup = cmds.rename(_dup, 'CAM')
        _dup = pom.CCamera(_dup)
        _dup.fix_shp_name()
        _dup.shp.plug['overscan'].set_locked(False)

        # Tag shape as tmp cam
        _dup.shp.add_attr('piniTmpCam', True)

        # More to world + parent constrain to cam to keep anim
        for _attr in 'trs':
            for _axis in 'xyz':
                _plug = '{}.{}{}'.format(_dup, _attr, _axis)
                cmds.setAttr(_plug, lock=False)
        if to_parent(_dup):
            cmds.parent(_dup, world=True)
        _cons = pom.CMDS.parentConstraint(self.cam, _dup)
        _LOGGER.info(' - CONS %s', _cons)
        set_col(_dup, 'green', force=True)
        _dup.u_scale(scale)

        # Move rotate axis off export cam
        _rot_axis = single(_dup.plug['rotateAxis'].get_val())
        _LOGGER.info(' - ROT AXIS %s', _rot_axis)
        _dup.plug['rotateAxis'].set_val([0, 0, 0])
        _cons.plug['target[0].targetOffsetRotate'].set_val(_rot_axis)

        # Connect shape attrs
        for _attr in self.cam_attrs:
            _src = pom.CCamera(self.cam).shp.to_plug(_attr)
            _trg = _dup.shp.to_plug(_attr)
            _trg.set_locked(False)
            _src.connect(_trg)

        set_namespace(":")

    def _export_img_planes(self):
        """Export image planes from this camera."""
        _LOGGER.info('EXPORT IMAGE PLANES %s', self.cam)

        _abc = self.to_output()
        _cam = pom.CCamera(self.cam)
        assert isinstance(_cam, pom.CCamera)

        # Write image plane settings to disk
        _img_planes = _cam.shp.cmds.listConnections(type='imagePlane')
        self._img_plane_data = {}
        for _img_plane in _img_planes:
            _name = _img_plane.clean_name
            _LOGGER.info(' - FOUND IMG PLANE %s %s', _name, _img_plane)
            _data = {}
            for _tag, _node in [
                    ('tfm', _img_plane),
                    ('shp', _img_plane.shp),
            ]:
                _file = _abc.to_dir().to_file(
                    '.pini/imgPlanes/{}_{}_{}.mel'.format(
                        _abc.base, _name, _tag))
                _node.save_preset(_file, force=True)
                assert _file.exists()
                _data[_tag] = _file.path
            self._img_plane_data[_name] = _data

    def pre_cache(self, extn='abc'):
        """Execute pre cache code.

        Args:
            extn (str): output extension
        """
        if extn == 'abc':
            self._build_tmp_cam()
            self._export_img_planes()

    def post_cache(self):
        """Build tmp CAM node."""
        del_namespace(self._tmp_ns, force=True)

    def rename(self, name):
        """Rename this camera.

        Args:
            name (str): new name to apply
        """
        if self.ref:
            self.ref.set_namespace(name)
        else:
            pom.CCamera(self.node).rename(name)

    def select_in_scene(self):
        """Select this camera in the current scene."""
        cmds.select(self.cam)

    def to_geo(self, extn='abc'):
        """Get list of nodes to cache from this camera.

        Args:
            extn (str): output extension

        Returns:
            (str list): geo nodes
        """
        if extn == 'abc':
            return [self._tmp_cam]
        if extn == 'fbx':
            return self.cam
        raise NotImplementedError

    def to_icon(self):
        """Get icon for this camera.

        Returns:
            (str): path to icon
        """
        return icons.find('Movie Camera')

    def to_job_arg(self, **kwargs):
        """Obtain AbcExport job arg for this cam.

        Returns:
            (str): job arg
        """
        return super(CPCacheableCam, self).to_job_arg(
            check_geo=False, **kwargs)


def find_cams():
    """Find cacheable cameras in the current scene.

    Returns:
        (CPCacheableCam list): cacheable cameras
    """
    _LOGGER.debug('FIND CAMS')
    _cams = []
    for _cam_s in cmds.ls(type="camera", allPaths=True):

        _LOGGER.debug('CHECKING %s', _cam_s)

        # Reject default cams
        _clean_s = re.split('[|:]', _cam_s)[-1]
        if _clean_s in DEFAULT_NODES:
            _LOGGER.debug(' - REJECTED DEFAULT %s', _cam_s)
            continue

        # Ignore tmp cache caches (maybe replace this later with attr check)
        _cam = single(cmds.listRelatives(_cam_s, parent=True, path=True))
        _ns = to_namespace(_cam)
        _LOGGER.debug(' - NS %s', _ns)
        if _ns and _ns.startswith('tmp_'):
            _LOGGER.debug(' - REJECTED NS')
            continue

        try:
            _cacheable = CPCacheableCam(_cam)
        except ValueError as _exc:
            _LOGGER.debug(' - REJECTED %s %s', _cam, _exc)
            continue

        _cams += [_cacheable]
    return _cams
