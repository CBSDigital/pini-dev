"""Tools for managing caching of cameras."""

import logging
import re

from maya import cmds

from pini import icons, dcc
from pini.utils import single, to_seq

from maya_pini import open_maya as pom
from maya_pini.utils import (
    DEFAULT_NODES, set_namespace, del_namespace, to_parent, set_col,
    to_clean, to_namespace)

from . import mpc_cacheable

_LOGGER = logging.getLogger(__name__)


class CPCacheableCam(mpc_cacheable.CPCacheable):  # pylint: disable=too-many-instance-attributes
    """Represents a camera that can be cached in the current scene."""

    ref = None
    cam_attrs = [
        'focalLength', 'focusDistance', 'filmTranslateH', 'filmTranslateV']
    attrs = cam_attrs + ['plateResX', 'plateResY']

    def __init__(self, cam, extn='abc'):
        """Constructor.

        Args:
            cam (str): camera transform
            extn (str): cache output extension
        """
        self.cam = cam

        _src_ref = _output_name = None
        if cmds.referenceQuery(self.cam, isNodeReferenced=True):
            _ns = to_namespace(self.cam)
            _src_ref = pom.find_ref(_ns)
            if not _src_ref:  # Could be nested in which case ignore
                raise ValueError(f'Failed to find reference {self.cam}')
            _output_name = _ns
        else:
            _output_name = to_clean(self.cam)

        self._tmp_ns = f':tmp_{_output_name}'
        self._tmp_cam = f'{self._tmp_ns}:CAM'
        self._img_plane_data = {}

        super().__init__(
            src_ref=_src_ref, node=cam, output_name=_output_name,
            output_type='cam', extn=extn)

    def build_metadata(self):
        """Obtain metadata dict for this cacheable.

        Returns:
            (dict): metadata
        """
        _data = super().build_metadata()
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
        _src_cam = pom.CCamera(self.cam)

        set_namespace(self._tmp_ns, clean=True)
        _dup_cam = cmds.duplicate(self.cam, name='CAM')[0]
        if to_clean(_dup_cam) != 'CAM':
            _dup_cam = cmds.rename(_dup_cam, 'CAM')
        _dup_cam = pom.CCamera(_dup_cam)
        _dup_cam.unhide(unlock=True)
        _dup_cam.fix_shp_name()
        _dup_cam.shp.plug['overscan'].set_locked(False)

        # Tag shape as tmp cam
        _dup_cam.shp.add_attr('piniTmpCam', True)

        # More to world + parent constrain to cam to keep anim
        _dup_cam.unlock_tfms()
        if to_parent(_dup_cam):
            cmds.parent(_dup_cam, world=True)
        _cons = pom.CMDS.parentConstraint(self.cam, _dup_cam)
        _LOGGER.info(' - CONS %s', _cons)
        set_col(_dup_cam, 'green', force=True)
        _dup_cam.u_scale(scale)

        # Move rotate axis off export cam
        _rot_axis = single(_dup_cam.plug['rotateAxis'].get_val())
        _LOGGER.info(' - ROT AXIS %s', _rot_axis)
        _dup_cam.plug['rotateAxis'].set_val([0, 0, 0])
        _cons.plug['target[0].targetOffsetRotate'].set_val(_rot_axis)

        # Connect shape attrs
        for _attr in self.cam_attrs:
            _src_attr = _src_cam.shp.to_plug(_attr)
            _trg_attr = _dup_cam.shp.to_plug(_attr)
            _trg_attr.set_locked(False)
            _src_attr.connect(_trg_attr)

        _add_plate_res_attrs(trg_cam=_dup_cam, src_cam=_src_cam)

        set_namespace(":")

    def _export_img_planes(self):
        """Export image planes from this camera."""
        _LOGGER.info('EXPORT IMAGE PLANES %s', self.cam)

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
                _file = self.output.to_dir().to_file(
                    f'.pini/imgPlanes/{self.output.base}_{_name}_{_tag}.mpa')
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

    def _set_name(self, name):
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

    def _to_icon(self):
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
        return super().to_job_arg(check_geo=False, **kwargs)


def _add_plate_res_attrs(src_cam, trg_cam):
    """Add plate res attrs to TMP cam.

    Args:
        src_cam (CCamera): source camera
        trg_cam (CCamera): tmp camera
    """
    _img = src_cam.shp.plug['imagePlane[0]'].find_incoming(plugs=False)
    _LOGGER.info(' - IMG %s', _img)
    if not _img:
        return

    _seq = to_seq(_img.shp.plug['imageName'].get_val())
    _LOGGER.info(' - SEQ %s', _seq)
    if not _seq:
        return
    _res = _seq.to_res()
    _LOGGER.info(' - RES %s', _res)
    _width, _height = _res.to_tuple()

    _res_x = trg_cam.add_attr('plateResX', _width)
    _LOGGER.info(' - ADDED RES X %s %s', _res_x, _width)
    _res_y = trg_cam.add_attr('plateResY', _height)
    _LOGGER.info(' - ADDED RES Y %s %s', _res_y, _height)


def find_cams(extn='abc'):
    """Find cacheable cameras in the current scene.

    Args:
        extn (str): cache output extension

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
            _cacheable = CPCacheableCam(_cam, extn=extn)
        except ValueError as _exc:
            _LOGGER.debug(' - REJECTED %s %s', _cam, _exc)
            continue

        _cams += [_cacheable]
    return _cams
