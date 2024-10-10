"""Tools for managing referenced pipeline files in maya.

NOTE: specifically maya references.
"""

# pylint: disable=no-member

import logging

from maya import cmds

from pini import pipe, dcc
from pini.utils import File, single, abs_path, cache_property, EMPTY

from maya_pini import open_maya as pom, tex, m_pipe
from maya_pini.m_pipe import lookdev
from maya_pini.utils import (
    restore_sel, del_namespace, to_node, to_shps, restore_ns, set_namespace)

from . import prm_base
from .. import pr_base

_LOGGER = logging.getLogger(__name__)


class CMayaRef(prm_base.CMayaPipeRef):
    """Pipelined maya file reference."""

    def __init__(self, ref_):
        """Constructor.

        Args:
            ref_ (FileRef): reference
        """
        self.ref = ref_
        super(CMayaRef, self).__init__(
            path=ref_.path, namespace=ref_.namespace)

    @property
    def is_loaded(self):
        """Test whether this reference is loaded.

        Returns:
            (bool): loaded state
        """
        return self.ref.is_loaded

    @property
    def lookdev(self):
        """Obtain lookdev reference for this abc.

        Returns:
            (CMayaShadersRef|None): lookdev ref (if any)
        """
        return dcc.find_pipe_ref(self.namespace+'_shd', catch=True)

    @property
    def node(self):
        """Obtain node for this reference.

        This is the top node if available, otherwise the reference node.

        Returns:
            (str): node
        """
        return self.ref.find_top_node(catch=True) or self.ref.ref_node

    @property
    def top_node(self):
        """Obtain this reference's top node.

        Returns:
            (CTransform): top node
        """
        return self.ref.top_node

    @restore_sel
    def attach_shaders(
            self, lookdev_=None, mode='Reference', tag=EMPTY, force=False):
        """Attach lookdev shaders to this abc.

        Args:
            lookdev_ (CPOutput|CMayaShadersRef): lookdev to attach
            mode (str): attach mode
             > Reference - reference nodes using <namespace>_shd namespace
             > Import - import nodes into root namespace
            tag (str): tag to apply
            force (bool): replace existing ref without confirmation
        """
        _LOGGER.info('ATTACH SHADERS %s', self)

        # Find lookdev ref
        if isinstance(lookdev_, CMayaShadersRef):
            _look_ref = lookdev_
        elif lookdev_ is None or isinstance(lookdev_, pipe.CPOutputFile):
            _look_out = lookdev_ or self.output.find_lookdev_shaders(tag=tag)
            if not _look_out:
                _LOGGER.info('NO LOOKDEV FOUND TO ATTACH %s', self)
                return
            _LOGGER.info(' - LOOKDEV OUT %s', _look_out)
            _look_ref = dcc.create_ref(
                _look_out, namespace=self.namespace+'_shd', force=force)
            _look_ref = dcc.find_pipe_ref(_look_ref.namespace)
        else:
            raise ValueError(lookdev_)
        _LOGGER.info(' - LOOKDEV REF %s', _look_ref)

        # Attach
        if mode in ('Reference', 'Import'):
            _look_ref.attach_to(self)
            if mode == 'Import':
                _look_ref.ref.import_()
                cmds.namespace(
                    moveNamespace=(_look_ref.namespace, ":"), force=True)
                del_namespace(_look_ref.namespace, force=True)
        else:
            raise ValueError(mode)

    def build_plates(self):
        """Build plates camera plates if any are stored in metadata."""
        _img_planes = self.output.metadata.get('img_plane')
        if not _img_planes:
            _LOGGER.info('NO IMAGE PLANES FOUND %s', self.output)
            return

        _LOGGER.info('BUILDING IMG PLANES %s', self.output)
        _cam = self.ref.to_node('CAM')
        assert isinstance(_cam, pom.CCamera)
        for _name, _data in _img_planes.items():

            _LOGGER.info(' - BUILDING %s', _name)

            # Build image planes
            _name = to_node(_name, namespace=self.ref.namespace)
            _img_plane = pom.CMDS.imagePlane(camera=_cam.node)
            _img_plane = _img_plane.rename(_name)

            # Apply cached settings
            for _node, _file in [
                    (_img_plane, _data['tfm']),
                    (_img_plane.shp, _data['shp']),
            ]:
                _node.load_preset(pipe.map_path(_file))

            # Update for image path in case of OS switch
            _plug = _img_plane.shp.plug['imageName']
            _cur_path = abs_path(_plug.get_val())
            _new_path = pipe.map_path(_cur_path)
            if _cur_path != _new_path:
                _plug.set_val(_new_path)
                _LOGGER.info(' - UPDATING PATH %s -> %s', _cur_path, _new_path)

    @restore_sel
    def delete(self, force=False):
        """Delete this reference.

        Args:
            force (bool): delete without confirmation
        """
        self.ref.delete(force=force)
        del_namespace(self.namespace, force=True)

    def find_shaders_ref(self):
        """Find shaders reference linked to this one.

        Returns:
            (CMayaShadersRef|None): shaders ref (if any)
        """
        _shd_refs = [
            _ref for _ref in dcc.find_pipe_refs()
            if isinstance(_ref, CMayaShadersRef)]
        for _shd_ref in _shd_refs:
            if self in _shd_ref.find_targets():
                return _shd_ref
        return None

    def rename(self, namespace):
        """Update this reference's namespace.

        Args:
            namespace (str): new namespace
        """
        self.ref.set_namespace(namespace)

    def select_in_scene(self):
        """Select this reference in the current scene."""
        cmds.select(self.ref.find_top_nodes())

    def to_node(self, node, catch=False):
        """Obtain a node with this reference's namespace applied.

        Args:
            node (str): clean node name
            catch (bool): no error if unable to cast node, just return None

        Returns:
            (str): node with namespace
        """
        try:
            return self.ref.to_node(node)
        except RuntimeError as _exc:
            if catch:
                return None
            raise _exc

    def update(self, out, reset=False):
        """Apply a new path to this reference.

        Args:
            out (str): output to apply
            reset (bool): make clean copy of reference (loses ref edits)
        """
        _LOGGER.debug(' - UPDATE %s', self)
        _LOGGER.debug('   - OUTPUT %s', out)

        if out.extn in ['ma', 'mb', 'abc', 'fbx']:

            # Determine grp/tfm
            _orig_out = self.output
            _mtx = self._to_mtx()
            _grp = self._to_parent()
            if reset:
                _grp = None
                if self.ref.top_node:
                    _grp = self.ref.top_node.to_parent()
                self.delete(force=True)
                return dcc.create_ref(
                    out, namespace=self.namespace, group=_grp)

            # Apply update
            self.ref.update(out)
            self._init_path_attrs(out)
            if _mtx and self.top_node:
                _mtx.apply_to(self.top_node)
            if _grp and self.top_node:
                self.top_node.add_to_grp(_grp)

            # Apply type dependent updates
            if out.content_type == 'VrmeshMa':
                _shds = self.find_shaders_ref()
                _LOGGER.info(' - FIND SHADERS %s', _shds)
                if _shds:
                    _shds.delete(force=True)
            elif out.content_type == 'ModelMa':
                if _orig_out.content_type == 'VrmeshMa':
                    _LOGGER.info(' - FIND SHADERS %s', _orig_out)
                    _shds = _orig_out.find_rep(content_type='ShadersMa')
                    _LOGGER.info(' - SHADERS %s', _shds)
                    self.attach_shaders(_shds)

            return self

        if out.type_ == 'ass_gz':
            _ns = self.namespace
            _grp = self.node.to_parent()
            _mtx = self.ref.top_node.to_m()
            _LOGGER.debug(' - MTX %s', _mtx)
            self.delete(force=True)
            _ref = dcc.create_ref(out, namespace=_ns, group=_grp)
            _LOGGER.debug(' - REF %s', _ref)
            _mtx.apply_to(_ref.node)
            return _ref

        raise NotImplementedError(out)


class CMayaShadersRef(CMayaRef):
    """Represents a referenced maya lookdev publish."""

    @cache_property
    def shd_data(self):
        """Obtain shading data from yml file.

        Returns:
            (dict): shading data
        """
        _shd_yml = self.output.metadata.get('shd_yml')
        if not _shd_yml:
            return None
        _shd_yml = pipe.map_path(_shd_yml)
        return File(_shd_yml).read_yml()

    def attach_to(self, target):
        """Attach this lookdev to the given abc.

        Args:
            target (CMayaRef): ref to attach shaders to
        """
        _LOGGER.debug('ATTACH %s -> %s', self, target)
        _LOGGER.debug(' - OUTPUT %s', self.output)
        assert isinstance(target, pr_base.CPipeRef)

        # Read data from yml
        _shd_yml = pipe.map_path(self.output.metadata['shd_yml'])
        _LOGGER.debug(' - SHD YML %s', _shd_yml)
        _data = File(_shd_yml).read_yml()
        _LOGGER.log(9, ' - PINI %s', self.output.pini_ver)
        _shd_data = self.shd_data['shds']
        _settings = self.shd_data['settings']

        self._apply_shaders(shds=_shd_data, target=target)
        self._apply_settings(settings=_settings, target=target)
        self._apply_override_sets(target=target)
        if _data.get('lights'):
            self._apply_lights(target)
        if _data.get('top_node_attrs'):
            self._apply_top_node_attrs(target)

        # Connect to target
        _LOGGER.info(' - CONNECT TOP NODE %s', target.top_node)
        if target.top_node:
            target.top_node.add_attr('shaders', self.ref.ref_node, force=True)

    def _apply_override_sets(self, target):
        """Add abc geometry to ai override sets.

        Args:
            target (CPipeRef): reference to get geometry from
        """
        _LOGGER.debug('APPLY AI OVERRIDE SETS ref=%s', target)

        # Obtain override sets from shd data
        _sets = self.shd_data.get('override_sets', {})
        if not _sets:
            # Legacy format - deprecated 10/07/24
            _sets = self.shd_data.get('ai_override_sets', {})

        # Rebuild sets with geo from this ref
        for _set_name, _clean_geos in _sets.items():

            _LOGGER.debug(' - APPLYING SET %s %s', _set_name, _clean_geos)

            # Find set
            _set = self.to_node(_set_name, catch=True)
            if not _set or not cmds.objExists(_set):
                _LOGGER.info('  - MISSING OVERRIDE SET %s', _set_name)
                continue

            # Find geos
            _geos = []
            for _geo in _clean_geos:
                _geo = target.to_node(_geo, catch=True)
                if not _geo or not cmds.objExists(_geo):
                    _LOGGER.debug('   - MISSING GEO %s', _geo)
                    continue
                _LOGGER.debug('   - ADDING GEO %s', _geo)
                _geos.append(_geo)

            _LOGGER.debug('   - GEOS %s', _geos)
            if _geos:
                cmds.sets(_geos, addElement=_set)

    @restore_ns
    def _apply_lights(self, target):
        """Apply lookdev lights to the given cache.

        Args:
            target (CReference):  reference to apply cache to
        """
        set_namespace(':'+self.namespace)
        _lights = self.to_node('LIGHTS').find_children()
        _LOGGER.debug(' - LIGHTS %s', _lights)
        for _light in _lights:

            _LOGGER.debug(' - LIGHT %s', _light)
            _trg = target.to_node(_light, catch=True)
            _LOGGER.debug('   - TRG %s', _trg)
            if _trg:

                # Build constraint
                _name = str(_light.clean_name)+'_CONS'
                _cons = self.ref.to_node(_name, fmt='str')
                _LOGGER.debug('   - CONS %s', _cons)
                if cmds.objExists(_cons):
                    cmds.delete(_cons)
                    _LOGGER.debug('   - DELETING EXISTING CONS')
                _trg.parent_constraint(_light, name=_name)

            # Set light enabled/disabled based on whether target exists
            _en = bool(_trg)
            _type = m_pipe.to_light_shp(_light).object_type()
            _plug = {'RedshiftPhysicalLight': 'on'}.get(_type, 'enabled')
            _light.set_visible(_en)
            _light.shp.plug[_plug].set_val(_en)

    def _apply_shaders(self, shds, target):
        """Apply shaders to target ref.

        Args:
            shds (dict): shaders data
            target (CMayaRef): ref to attach shaders to
        """
        for _shd, _data in shds.items():

            _LOGGER.log(9, ' - SHD %s', _shd)

            # Obtain shader + shading engine
            if _shd == 'lambert1':
                _shd = 'lambert1'
            else:
                _shd = self.ref.to_node(_shd)
            if not cmds.objExists(_shd):
                raise RuntimeError('Missing shader '+_shd)

            # Find shading engine
            _ses = cmds.listConnections(_shd, type='shadingEngine') or []
            _ses = sorted(set(_ses))
            _se = single(_ses, catch=True)
            if not _se:
                _name = _shd+"SG"
                _se = cmds.sets(
                    name=_name, renderable=True, noSurfaceShader=True,
                    empty=True)
                cmds.connectAttr(_shd+'.outColor', _se+'.surfaceShader')
            _LOGGER.log(9, '   - SE %s', _se)
            assert _se

            # Attach geos
            _LOGGER.log(9, '   - GEOS %s', _data['geos'])
            for _item in _data['geos']:

                # Check if node exists in abc
                _node = target.ref.to_node(_item, catch=True)
                if not _node:
                    _LOGGER.info('   - MISSING NODE %s', _item)
                    continue

                # Get list of shapes
                _type = cmds.objectType(_node)
                _LOGGER.log(9, '     - GEO %s %s', _node, _type)
                if _type == 'transform':
                    _shps = to_shps(str(_node))
                elif _type == 'mesh':
                    _shps = [_node]
                else:
                    raise ValueError(_node, _type)
                _LOGGER.log(9, '       - SHPS %s', _shps)

                # Add shapes to shading engine
                for _shp in _shps:
                    _LOGGER.log(9, '       - SHP %s', _shp)
                    cmds.sets(_shp, edit=True, forceElement=_se)

    def _apply_settings(self, settings, target):
        """Apply lookdev settings to target ref.

        Args:
            settings (dict): settings data
            target (CMayaRef): ref to attach shaders to
        """
        _LOGGER.debug('APPLY SETTINGS %s %s', target, settings)
        _ref = target.ref
        _to_apply = []
        for _key, _data in settings.items():

            _LOGGER.debug(' - APPLY SETTING %s %s', _key, _data)

            _name, _settings = _key, _data
            _tfm = _ref.to_node(_name, catch=True)
            if not _tfm:
                _LOGGER.warning(' - MISSING NODE %s', _name)
                continue
            for _shp in _tfm.to_shps():
                for _attr, _val in _settings.items():
                    if _attr.startswith('vray'):
                        lookdev.check_vray_mesh_setting(mesh=_shp, attr=_attr)
                    _plug = _shp.plug[_attr]
                    _LOGGER.debug('   - APPLY VALUE %s %s', _plug, _val)
                    _plug.set_val(_val)

    def _apply_top_node_attrs(self, target):
        """Apply top node attributes.

        eg. colour switch on top node.

        Args:
            target (CMayaRef): ref to attach shaders to
        """
        _attrs = self.shd_data['top_node_attrs']
        _LOGGER.info('APPLY TOP NODE ATTRS %s', _attrs)
        _dummy = self.to_node('DummyTopNode')
        _LOGGER.info(' - DUMMY %s', _dummy)
        for _attr in _attrs:
            _dummy_plug = _dummy.plug[_attr]
            _LOGGER.info(' - ATTR %s', _dummy_plug)
            _new_plug = target.top_node.add_attr(
                _attr, _dummy_plug.get_val(), min_val=_dummy_plug.get_min(),
                max_val=_dummy_plug.get_max())
            _new_plug.connect(_dummy_plug)

    def find_target(self):
        """Find this lookdev's target.

        Returns:
            (CMayaRef): lookdev target
        """
        return single(self.find_targets(), catch=True)

    def find_targets(self, from_top_node=False, from_assignments=False):
        """Find references using this lookdev (eg. abcs).

        Args:
            from_top_node (bool): check top node shaders attribute for
                linked shaders reference
            from_assignments (bool): try to find targets from shading
                assignments (can be slow for heavy scenes)

        Returns:
            (CMayaPipeRef list): references
        """
        _LOGGER.log(9, 'FIND TARGETS %s', self)
        _trgs = set()

        # Find target by name
        if self.namespace.endswith('_shd'):
            _name_match = self.namespace[:-4]
            _trg = dcc.find_pipe_ref(namespace=_name_match, catch=True)
            _LOGGER.log(9, ' - NAME MATCH %s %s', _name_match, _trg)
            if _trg:
                _trgs.add(_trg)
        _LOGGER.log(9, ' - TRGS (A) %s', sorted(_trgs))

        # Find by shaders link
        if from_top_node:
            for _ref in dcc.find_pipe_refs():
                if _ref in [self] + sorted(_trgs):
                    continue
                if self._ref_has_top_node_link(_ref):
                    _trgs.add(_ref)
            _LOGGER.log(9, ' - TRGS (B) %s', sorted(_trgs))

        # Find targets based on shader
        if from_assignments:
            for _se in self.ref.find_nodes(type_='shadingEngine'):
                _shd = tex.to_shd(_se)
                _LOGGER.log(9, ' - SHD %s %s', _se, _shd)
                for _geo in _shd.to_geo():
                    if not _geo.is_referenced():
                        continue
                    _ref = pom.CReference(_geo)
                    _ref = dcc.find_pipe_ref(_ref.namespace, catch=True)
                    if not _ref:
                        continue
                    _LOGGER.log(9, '   - GEO %s %s', _geo, _ref)
                    _trgs.add(_ref)
            _LOGGER.log(9, ' - TRGS (C) %s', sorted(_trgs))

        return sorted(_trgs)

    def _ref_has_top_node_link(self, ref_):
        """Check with the given reference's top node is linked to this.

        Args:
            ref_ (CMayaRef): reference to check

        Returns:
            (bool): whether linked
        """
        if not ref_.top_node:
            return False

        # Find attached reference
        if not ref_.top_node.has_attr('shaders'):
            return False
        _LOGGER.log(9, ' - CHECK REF %s', ref_)
        _shd_plug = ref_.top_node.plug['shaders']
        _shd_rn = _shd_plug.find_incoming(plugs=False)
        if not _shd_rn:
            return False

        # Compare attached ref namespace
        _LOGGER.log(9, '   - SHD PLUG %s %s', _shd_plug, _shd_rn)
        _shd_ref = pom.CReference(_shd_rn)
        _LOGGER.log(9, '   - SHD %s', _shd_ref)

        return _shd_ref.namespace == self.namespace

    def update(self, out, reset=True):
        """Apply a new path to this reference.

        Args:
            out (str): output to apply
            reset (bool): make clean copy of reference (loses ref edits which
                is safer for lookdev as shader assignments can get confused
                with stale edits)
        """
        _LOGGER.info('UPDATE %s %s', self, out)
        _result = super(CMayaShadersRef, self).update(out, reset=reset)
        for _trg in self.find_targets():
            _LOGGER.info(' - ATTACH TO %s', _trg)
            _result.attach_to(_trg)
        return _result


def read_reference_pipe_refs(selected=False):
    """Read pipeline refs in references.

    Args:
        selected (bool): only find selected refs

    Returns:
        (CMayaRef list): referenced pipe refs
    """
    _LOGGER.log(9, 'READ REFERENCE PIPE REFS')

    _all_refs = pom.find_refs(selected=selected)
    _LOGGER.log(9, ' - FOUND %d REFS', len(_all_refs))

    _refs = []
    for _ref in _all_refs:

        _LOGGER.log(9, ' - TESTING %s %s', _ref, _ref.path)

        # Obtain output
        _out = pipe.to_output(_ref.path, catch=True)
        if not _out:
            _LOGGER.log(9, '   - NOT VALID OUTPUT %s', _ref.path)
            continue
        _LOGGER.log(9, '   - OUT %s', _ref)

        # Obtained cache output
        _out_c = pipe.CACHE.obt_output(_out, catch=True)
        if not _out_c:
            _LOGGER.log(9, '   - MISSING FROM CACHE')
            continue

        # Determine class based on publish type
        if _out_c.content_type == 'ShadersMa':
            _class = CMayaShadersRef
        else:
            _class = CMayaRef
        _ref = _class(_ref)
        _LOGGER.log(9, '   - VALID REF %s', _ref)
        _refs.append(_ref)

    return _refs
