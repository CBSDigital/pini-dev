"""Tools for managing pipelined references in maya."""

import logging

from maya import cmds

from pini import pipe, dcc
from pini.utils import (
    File, single, abs_path, cache_property, Seq, passes_filter,
    file_to_seq)

from maya_pini import open_maya as pom, tex
from maya_pini.utils import (
    restore_sel, del_namespace, to_node, to_shps, restore_ns, set_namespace)

from . import pr_base

_LOGGER = logging.getLogger(__name__)


class _CMayaPipeRef(pr_base.CPipeRef):
    """Base class for any pipelined maya reference."""

    def delete(self, force=False):
        """Delete this reference.

        Args:
            force (bool): delete without confirmation
        """
        raise NotImplementedError(self)


class CMayaReference(_CMayaPipeRef):
    """Pipelined maya file reference."""

    def __init__(self, ref_):
        """Constructor.

        Args:
            ref_ (FileRef): reference
        """
        self.ref = ref_
        super(CMayaReference, self).__init__(
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
            (CMayaLookdevRef|None): lookdev ref (if any)
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
    def attach_lookdev(self, lookdev=None, mode='Reference'):
        """Attach lookdev shaders to this abc.

        Args:
            lookdev (CPOutput|CMayaLookdevRef): lookdev to attach
            mode (str): attach mode
             > Reference - reference nodes using <namespace>_shd namespace
             > Import - import nodes into root namespace
        """
        _LOGGER.info('ATTACH LOOKDEV %s', self)

        # Find lookdev ref
        if isinstance(lookdev, CMayaLookdevRef):
            _look_ref = lookdev
        elif lookdev is None or isinstance(lookdev, pipe.CPOutput):
            _look_out = lookdev or self.output.find_lookdev()
            if not _look_out:
                _LOGGER.info('NO LOOKDEV FOUND TO ATTACH %s', self)
                return
            _LOGGER.info(' - LOOKDEV OUT %s', _look_out)
            _look_ref = dcc.create_ref(
                _look_out, namespace=self.namespace+'_shd')
            _look_ref = dcc.find_pipe_ref(_look_ref.namespace)
        else:
            raise ValueError(lookdev)
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

    def rename(self, namespace):
        """Update this reference's namespace.

        Args:
            namespace (str): new namespace
        """
        self.ref.set_namespace(namespace)

    def select_in_scene(self):
        """Select this reference in the current scene."""
        cmds.select(self.ref.find_top_nodes())

    def swap_rep(self, output):
        """Swap this reference for a different representation.

        Args:
            output (CPOutput): representation to swap to
        """
        raise NotImplementedError

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

    def update(self, out):
        """Apply a new path to this reference.

        Args:
            out (str): output to apply
        """
        _LOGGER.debug('UPDATE %s', self)
        _LOGGER.debug(' - OUTPUT %s', out)
        if out.extn in ['ma', 'mb', 'abc', 'fbx']:
            self.ref.update(out)
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


class CMayaLookdevRef(CMayaReference):
    """Represents a referenced maya lookdev publish."""

    @cache_property
    def shd_data(self):
        """Obtain shading data from yml file.

        Returns:
            (dict): shading data
        """
        _shd_yml = pipe.map_path(self.output.metadata['shd_yml'])
        return File(_shd_yml).read_yml()

    def attach_to(self, ref_):
        """Attach this lookdev to the given abc.

        Args:
            ref_ (CMayaReference): ref_ to attach shaders to
        """
        _LOGGER.debug('ATTACH %s -> %s', self, ref_)
        assert isinstance(ref_, pr_base.CPipeRef)

        # Read data from yml
        _shd_yml = pipe.map_path(self.output.metadata['shd_yml'])
        _data = File(_shd_yml).read_yml()
        _LOGGER.debug(' - PINI %s', self.output.pini_ver)
        _shd_data = self.shd_data['shds']
        _settings = self.shd_data['settings']

        self._apply_shaders(shds=_shd_data, ref_=ref_)
        self._apply_settings(settings=_settings, ref_=ref_)
        self._apply_ai_override_sets(ref_=ref_)
        if _data.get('lights'):
            self._apply_lights(ref_)

    def _apply_ai_override_sets(self, ref_):
        """Add abc geometry to ai override sets.

        Args:
            ref_ (CPipeRef): reference to get geometry from
        """
        _LOGGER.debug('APPLY AI OVERRIDE SETS ref=%s', ref_)
        _sets = self.shd_data.get('ai_override_sets', {})  # pylint: disable=no-member

        for _set, _clean_geos in _sets.items():

            _LOGGER.debug(' - APPLYING SET %s %s', _set, _clean_geos)

            # Find set
            _set = self.to_node(_set)
            if not cmds.objExists(_set):
                _LOGGER.debug('  - MISSING SET')
                continue

            # Find geos
            _geos = []
            for _geo in _clean_geos:
                _geo = ref_.to_node(_geo)
                if not cmds.objExists(_geo):
                    _LOGGER.debug('   - MISSING GEO %s', _geo)
                    continue
                _LOGGER.debug('   - ADDING GEO %s', _geo)
                _geos.append(_geo)

            _LOGGER.debug('   - GEOS %s', _geos)
            if _geos:
                cmds.sets(_geos, addElement=_set)

    @restore_ns
    def _apply_lights(self, ref_):
        """Apply lookdev lights to the given cache.

        Args:
            ref_ (CReference):  reference to apply cache to
        """
        set_namespace(':'+self.namespace)
        _lights = self.to_node('LIGHTS').find_children()
        _LOGGER.debug(' - LIGHTS %s', _lights)
        for _light in _lights:

            _LOGGER.debug(' - LIGHT %s', _light)
            _trg = ref_.to_node(_light, catch=True)
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
            _type = _light.shp.object_type()
            _plug = {'RedshiftPhysicalLight': 'on'}.get(_type, 'enabled')
            _light.set_visible(_en)
            _light.shp.plug[_plug].set_val(_en)

    def _apply_shaders(self, shds, ref_):
        """Apply shaders to target ref.

        Args:
            shds (dict): shaders data
            ref_ (CMayaReference): ref_ to attach shaders to
        """
        for _shd, _data in shds.items():

            _LOGGER.debug(' - SHD %s', _shd)

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
            _LOGGER.debug('   - SE %s', _se)
            assert _se

            # Attach geos
            _LOGGER.debug('   - GEOS %s', _data['geos'])
            for _item in _data['geos']:

                # Check if node exists in abc
                _node = ref_.ref.to_node(_item, catch=True)
                if not _node:
                    _LOGGER.info('   - MISSING NODE %s', _item)
                    continue

                # Get list of shapes
                _type = cmds.objectType(_node)
                _LOGGER.debug('     - GEO %s %s', _node, _type)
                if _type == 'transform':
                    _shps = to_shps(str(_node))
                elif _type == 'mesh':
                    _shps = [_node]
                else:
                    raise ValueError(_node, _type)
                _LOGGER.debug('     - SHPS %s', _shps)

                # Add shapes to shading engine
                for _shp in _shps:
                    _LOGGER.debug('     - SHP %s', _shp)
                    cmds.sets(_shp, edit=True, forceElement=_se)

    def _apply_settings(self, settings, ref_):
        """Apply lookdev settings to target ref.

        Args:
            settings (dict): settings data
            ref_ (CMayaReference): ref_ to attach shaders to
        """
        _ref = ref_.ref
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
                    _plug = _shp.plug[_attr]
                    _LOGGER.debug('   - APPLY VALUE %s %s', _plug, _val)
                    _plug.set_val(_val)

    def find_target(self):
        """Find this lookdev's target.

        Returns:
            (CMayaReference): lookdev target
        """
        return single(self.find_targets(), catch=True)

    def find_targets(self):
        """Find references using this lookdev (eg. abcs).

        Returns:
            (CReference list): references
        """
        _refs = set()

        # Find target by name
        if self.namespace.endswith('_shd'):
            _trg = dcc.find_pipe_ref(
                namespace=self.namespace[:-4], catch=True)
            if _trg:
                _refs.add(_trg)

        # Find targets based on shader
        for _se in self.ref.find_nodes(type_='shadingEngine'):
            _shd = tex.to_shd(_se)
            _LOGGER.debug(' - SHD %s %s', _se, _shd)
            for _geo in _shd.to_geo():
                if not _geo.is_referenced():
                    continue
                _ref = pom.CReference(_geo)
                _ref = dcc.find_pipe_ref(_ref.namespace, catch=True)
                if not _ref:
                    continue
                _LOGGER.debug('   - GEO %s %s', _geo, _ref)
                _refs.add(_ref)

        return sorted(_refs)

    def swap_rep(self, output):
        """Swap this reference for a different representation.

        Args:
            output (CPOutput): representation to swap to
        """
        raise NotImplementedError

    def update(self, out):
        """Apply a new path to this reference.

        Args:
            out (str): output to apply
        """
        _result = super(CMayaLookdevRef, self).update(out)
        for _trg in self.find_targets():
            self.attach_to(_trg)
        return _result


class CMayaVdb(_CMayaPipeRef):
    """Represents a pipeline vdb reference in an aiVolume node."""

    ref = None

    def __init__(self, node, path=None):
        """Constructor.

        Args:
            node (CTransform): aiVolume transform
            path (str): override path - maya seems to only read the
                vdb if useFileSequence is disabled but then it seems
                to update it in a deferred thread; this allows the path
                to be hacked so a valid vdb ref can be built on create
        """
        self.node = node
        assert isinstance(self.node, pom.CTransform)
        assert self.node.shp.object_type() == 'aiVolume'
        _path = self.node.shp.plug['filename'].get_val() or ''
        _path = _path.replace('.####.', '.%04d.')
        if not _path:
            raise ValueError('Empty path')

        super(CMayaVdb, self).__init__(path or _path, namespace=str(self.node))

    def delete(self, force=False):
        """Delete this node.

        Args:
            force (bool): delete without confirmation
        """
        if not force:
            raise NotImplementedError
        cmds.delete(self.node)

    def swap_rep(self, output):
        """Swap this reference for a different representation.

        Args:
            output (CPOutput): representation to swap to
        """
        raise NotImplementedError

    def update(self, out):
        """Update this node to a new output.

        Args:
            out (CPOutputSeq): new volume to apply
        """
        assert isinstance(out, Seq)
        _path = out.path.replace('.%04d.', '.####.')
        self.node.shp.plug['filename'].set_val(_path)


class CMayaAiStandIn(_CMayaPipeRef):
    """Represents a pipeline ass/usd reference in an aiStandIn node."""

    ref = None

    def __init__(self, node, path=None):
        """Constructor.

        Args:
            node (CTransform): aiStandIn node
            path (str): override path - to accommodate arnold delayed update
        """
        _LOGGER.debug('INIT CMayaAiStandIn %s %s', node, path)
        self.node = node
        assert isinstance(self.node, pom.CTransform)
        assert self.node.shp.object_type() == 'aiStandIn'

        # Update path to %04d format
        _path = self.node.shp.plug['dso'].get_val()
        _path = _path.replace('.####.', '.%04d.')
        if '.%04d.' not in _path:
            _seq = file_to_seq(_path, catch=True)
            if _seq:
                _path = _seq.path

        _LOGGER.debug(' - PATH %s', _path)
        super(CMayaAiStandIn, self).__init__(
            path or _path, namespace=str(self.node))

    def delete(self, force=False):
        """Delete this node.

        Args:
            force (bool): delete without confirmation
        """
        if not force:
            raise NotImplementedError
        cmds.delete(self.node)

    def swap_rep(self, output):
        """Swap this reference for a different representation.

        Args:
            output (CPOutput): representation to swap to
        """
        raise NotImplementedError

    def update(self, out):
        """Update this node to a new output.

        Args:
            out (CPOutput|CPOutputSeq): new standin to apply
        """
        _LOGGER.debug('UPDATE %s %s', self, out)
        if out.extn in ['ass', 'abc', 'usd', 'gz']:
            _path = out.path.replace('.%04d.', '.####.')
            self.node.shp.plug['dso'].set_val(_path)
            return CMayaAiStandIn(self.node)
        if out.extn in ('ma', 'mb'):
            _grp = self.node.to_parent()
            _ns = self.namespace
            _mtx = self.node.to_m()
            self.delete(force=True)
            _ref = dcc.create_ref(out, namespace=_ns, group=_grp)
            _mtx.apply_to(_ref.ref.top_node)
            return _ref
        raise NotImplementedError(out)


def _read_reference_pipe_refs(selected=False):
    """Read pipeline refs in references.

    Args:
        selected (bool): only find selected refs

    Returns:
        (CMayaReference list): referenced pipe refs
    """
    _LOGGER.debug('READ REFERENCE PIPEREFS')

    _all_refs = pom.find_refs(selected=selected)

    _refs = []
    for _ref in _all_refs:

        _LOGGER.debug('TESTING %s', _ref)

        # Obtain output
        _out = pipe.to_output(_ref.path, catch=True)
        if not _out:
            _LOGGER.debug(' - NOT VALID OUTPUT %s', _ref.path)
            continue
        _LOGGER.debug(' - OUT %s', _ref)

        # Obtained cache output
        try:
            _out_c = pipe.CACHE.obt_output(_out)
        except ValueError:
            _LOGGER.debug(' - MISSING FROM CACHE')
            continue

        # Determine class based on publish type
        _pub_type = _out_c.metadata.get('publish_type')
        _LOGGER.debug(' - PUB TYPE %s', _pub_type)
        if _pub_type == 'CMayaLookdevPublish':
            _class = CMayaLookdevRef
        else:
            _class = CMayaReference
        _ref = _class(_ref)
        _refs.append(_ref)

    return _refs


def _read_vdb_pipe_refs(selected=False):
    """Read pipeline vdb refs.

    Args:
        selected (bool): only find selected refs

    Returns:
        (CMayaVdb list): vdb refs
    """
    _LOGGER.debug('READ VDB PIPE REFS')

    if 'aiVolume' not in cmds.allNodeTypes():
        return []

    # Get list of aiVolume nodes
    if selected:
        _aivs = []
        for _node in pom.CMDS.ls(selection=True):
            _type = _node.object_type()
            _LOGGER.debug(' - CHECKING NODE %s %s', _node, _type)
            if _type == 'aiVolume':
                _aivs.append(_node)
            elif _type == 'transform':
                _shp = _node.to_shp(catch=True)
                if _shp:
                    _shp_type = _shp.object_type()
                    _LOGGER.debug('   - CHECKING SHP %s %s', _shp, _shp_type)
                    if _shp_type == 'aiVolume':
                        _aivs.append(_shp)
    else:
        _aivs = pom.CMDS.ls(type='aiVolume')

    # Map to CMayaVdb objects
    _vdbs = []
    for _aiv_s in _aivs:
        _aiv = _aiv_s.to_parent()
        try:
            _vdb = CMayaVdb(_aiv)
        except ValueError:
            continue
        _vdbs.append(_vdb)
    return _vdbs


def _read_aistandin_pipe_refs(selected=False):
    """Find pipelined aiStandIn references in the current scene.

    Args:
        selected (bool): return selected only

    Returns:
        (CMayaAiStandIn list): aiStandIn refs
    """
    _LOGGER.debug('READ AISTANDIN PIPE REFS')

    if 'aiStandIn' not in cmds.allNodeTypes():
        return []

    # Get list of aiStandIn nodes
    if selected:
        _ais_ss = []
        for _node in pom.get_selected(multi=True):
            _type = _node.object_type()
            _LOGGER.debug(' - CHECKING NODE %s %s', _node, _type)
            if _type == 'aiStandIn':
                _ais_ss.append(_node)
            elif _type == 'transform':
                _shp = _node.to_shp(catch=True)
                if _shp:
                    _shp_type = _shp.object_type()
                    _LOGGER.debug('   - CHECKING SHP %s %s', _shp, _shp_type)
                    if _shp_type == 'aiStandIn':
                        _ais_ss.append(_shp)
    else:
        _ais_ss = pom.CMDS.ls(type='aiStandIn', selection=selected)
    _LOGGER.debug(' - FOUND %d AISTANDINS %s', len(_ais_ss), _ais_ss)

    # Map to CMayaAiStandIn objects
    _asses = []
    for _ais_s in _ais_ss:
        _ais = _ais_s.to_parent()
        _LOGGER.debug(' - TESTING %s', _ais)
        try:
            _ass = CMayaAiStandIn(_ais)
        except ValueError as _exc:
            _LOGGER.debug('   - REJECTED %s', _exc)
            continue
        _LOGGER.debug('   - ACCEPTED %s', _ass)
        _asses.append(_ass)

    return _asses


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
    _refs += _read_reference_pipe_refs(selected=selected)
    _refs += _read_vdb_pipe_refs(selected=selected)
    _refs += _read_aistandin_pipe_refs(selected=selected)

    if extn:
        _refs = [_ref for _ref in _refs if _ref.extn == extn]
    if filter_:
        _refs = [_ref for _ref in _refs
                 if passes_filter(_ref.namespace, filter_)]

    return _refs
