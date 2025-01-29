"""Tools for managing maya publish handlers."""

import copy
import logging
import os

from maya import cmds

from pini import pipe, dcc, qt
from pini.utils import single, File, abs_path, passes_filter, to_seq, Seq, TMP

from maya_pini import ref, m_pipe, open_maya as pom
from maya_pini.m_pipe import lookdev
from maya_pini.utils import (
    restore_sel, DEFAULT_NODES, to_long, to_namespace, save_scene,
    save_redshift_proxy, disable_scanner_callbacks)

from .. import ph_basic

_LOGGER = logging.getLogger(__name__)


class CMayaLookdevPublish(ph_basic.CBasicPublish):
    """Manages a maya lookdev publish."""

    NAME = 'Maya Lookdev Publish'
    LABEL = '\n'.join([
        ' - Builds lookdev files for abc attach',
        ' - Shaders are stored in maya file and attached using yml',
        ' - Nodes in JUNK group are ignored',
        ' - Any sets in overrides_SET are saved and restored on abc attach',
    ])
    ACTION = 'LookdevPublish'

    shd_yml = None
    textures = None

    def build_ui(self, parent=None, layout=None, add_footer=True):
        """Build basic render interface into the given layout.

        Args:
            parent (QWidget): parent widget
            layout (QLayout): layout to add widgets to
            add_footer (bool): add footer elements
        """
        super().build_ui(
            parent=parent, layout=layout, add_footer=False)

        self.add_separator_elem()
        self._build_pxy_opts()
        if add_footer:
            self.add_footer_elems()

    def _build_pxy_opts(self):
        """Build proxy publish options."""
        _ass = 'arnold' in dcc.allowed_renderers()
        _vrm = 'vray' in dcc.allowed_renderers()
        _rs = 'redshift' in dcc.allowed_renderers()

        self.ui.ExportAss = None
        self.ui.ExportVrmesh = None
        self.ui.ExportRedshiftProxy = None

        if not (_ass or _vrm or _rs):
            return

        if _ass:
            self.ui.ExportAss = self.add_checkbox_elem(
                val=True, name='ExportAss',
                label="Export ass.gz of geo")
        if _vrm:
            self.ui.ExportVrmesh = self.add_checkbox_elem(
                val=True, name='ExportVrmesh',
                label="Export shaded vrmesh scene of geo")
        if _rs:
            self.ui.ExportRedshiftProxy = self.add_checkbox_elem(
                val=True, name='ExportRedshiftProxy',
                label="Export redshift proxy of geo")

        if _vrm or _rs:
            self.ui.ProxyAnim = self.add_checkbox_elem(
                val=False, name='ProxyAnim',
                label='Include animation in proxies')

        self.add_separator_elem()

    def build_metadata(
            self, work=None, sanity_check_=True, task='lookdev', force=False):
        """Obtain publish metadata.

        Args:
            work (CPWork): override workfile to read metadata from
            sanity_check_ (bool): run sanity checks before publish
            task (str): task to pass to sanity check
            force (bool): force completion without any confirmations

        Returns:
            (dict): metadata
        """
        _data = super().build_metadata(
            work=work, sanity_check_=sanity_check_, task=task, force=force)
        del _data['range']
        if self.shd_yml:
            _data['shd_yml'] = self.shd_yml.path
        return _data

    @restore_sel
    def publish(self, work=None, force=False, version_up=None):
        """Execute lookdev publish.

        Args:
            work (CPWork): override publish work file
            force (bool): force overwrite without confirmation
            version_up (bool): version up on publish

        Returns:
            (CPOutput): publish file
        """
        _LOGGER.info('LOOKDEV PUBLISH')

        _work = work or pipe.CACHE.obt_cur_work()
        _pub = _work.to_output('publish', output_type='lookdev', extn='ma')
        _data_dir = _pub.to_dir().to_subdir('data')
        _metadata = self.build_metadata(force=force)

        self.shd_yml = _pub.to_file(
            dir_=_data_dir,  base=_pub.base+'_shaders', extn='yml')
        _LOGGER.info(' - SHD YML %s', self.shd_yml)

        _bkp = _work.save(
            reason='lookdev publish', force=True, update_outputs=False)
        _metadata['bkp'] = _bkp.path

        # Check scene
        _clean_junk()
        _assignments = lookdev.read_shader_assignments(referenced=False)
        if not _assignments:
            if lookdev.read_shader_assignments(referenced=True):
                raise RuntimeError('Referenced shaders are not supported')
            raise RuntimeError('No valid shading assignments found')
        for _shd in _assignments:
            if to_namespace(_shd):
                raise RuntimeError('Shader has namespace '+_shd)
        self.textures = _read_textures()

        # Generate outputs
        _outs = []
        _ass = self._handle_export_ass(force=force, metadata=_metadata)
        if _ass:
            _outs.append(_ass)
        _vrm_ma = self._handle_export_vrm_ma(
            force=force, metadata=_metadata)
        if _vrm_ma:
            _outs.append(_vrm_ma)
        _rs_pxy = self._handle_export_rs_pxy(
            force=force, metadata=_metadata, work=_work)
        if _rs_pxy:
            _outs.append(_rs_pxy)
        self._handle_export_shaders_scene(
            output=_pub, force=force, metadata=_metadata)
        _outs.append(_pub)

        _work.load(force=True)
        self.post_export(work=_work, outs=_outs, version_up=version_up)

        return _outs

    def _handle_export_ass(self, metadata, force):
        """Handle export ass file.

        Args:
            metadata (dict): publish metadata
            force (bool): overwrite without confirmation

        Returns:
            (CPOutput|None): output (if any)
        """
        if self.ui and self.ui.ExportAss:
            _tgl_export_ass = self.ui.ExportAss.isChecked()
        else:
            _tgl_export_ass = 'arnold' in dcc.allowed_renderers()

        _ass = None
        if _tgl_export_ass:
            _ass = _export_ass(metadata=metadata, force=force)

        return _ass

    def _handle_export_vrm_ma(self, metadata, force):
        """Handle export vray mesh ma file.

        Args:
            metadata (dict): publish metadata
            force (bool): overwrite without confirmation

        Returns:
            (CPOutput|None): output (if any)
        """
        if self.ui and self.ui.ExportVrmesh:
            _tgl_export_vrm = self.ui.ExportVrmesh.isChecked()
            _anim = self.ui.ProxyAnim.isChecked()
        else:
            _tgl_export_vrm = 'vray' in dcc.allowed_renderers()
            _anim = False

        _vrm_ma = None
        if _tgl_export_vrm:
            _metadata = copy.deepcopy(metadata)
            _metadata['animated'] = _anim
            _vrm_ma = lookdev.export_vrmesh_ma(
                metadata=_metadata, force=force, animation=_anim)

        return _vrm_ma

    def _handle_export_rs_pxy(self, work, metadata, force):
        """Handle export redshift proxy file.

        Args:
            work (CPWork): publish work file
            metadata (dict): publish metadata
            force (bool): overwrite without confirmation

        Returns:
            (CPOutput|None): output (if any)
        """
        if self.ui and self.ui.ExportVrmesh:
            _tgl_export_rs_pxy = self.ui.ExportRedshiftProxy.isChecked()
            _anim = self.ui.ProxyAnim.isChecked()
        else:
            _tgl_export_rs_pxy = 'redshift' in dcc.allowed_renderers()
            _anim = False

        if not _tgl_export_rs_pxy:
            return None

        _tmpl = 'publish' if not _anim else 'publish_seq'
        _rs_pxy = work.to_output(
            _tmpl, output_type='redshiftProxy', extn='rs')
        _LOGGER.info(' - PXY %s %s', _tmpl, _rs_pxy)

        # Select export geo
        _select = m_pipe.find_cache_set()
        if not _select:
            _assigns = lookdev.read_shader_assignments()
            _select = sorted(set(sum(
                [_item['geos'] for _item in _assigns.values()], [])))
        if not _select:
            raise RuntimeError('No geo found')
        _LOGGER.info(' - RS SELECT GEO %s', _select)
        cmds.select(_select)

        # Execute export
        try:
            save_redshift_proxy(
                _rs_pxy, selection=True, animation=_anim, force=force)
        except RuntimeError as _exc:
            _LOGGER.error('FAILED TO EXPORT REDSHIFT PROXY %s', _exc)
            return None

        _metadata = copy.deepcopy(metadata)
        _metadata['animated'] = _anim
        _rs_pxy.set_metadata(_metadata)

        return _rs_pxy

    def _handle_export_shaders_scene(self, output, metadata, force):
        """Handle export shaders ma file.

        Args:
            output (CPOutput): publish file
            metadata (dict): publish metadata
            force (bool): overwrite without confirmation

        Returns:
            (CPOutput|None): output (if any)
        """

        # Read shaders + save to yml
        _shd_data = lookdev.read_publish_metadata()
        self.shd_yml.write_yml(_shd_data, force=True, fix_unicode=True)
        _LOGGER.info(' - WROTE SHD YML %s', self.shd_yml)

        # Export shaders scene
        _export_nodes = lookdev.find_export_nodes()
        _flush_scene(keep_nodes=_export_nodes)
        _export_nodes = [  # Empty sets are deleted on import ref (?)
            _node for _node in _export_nodes if cmds.objExists(_node)]
        cmds.select(_export_nodes, noExpand=True)
        if not _export_nodes:
            raise RuntimeError('No shaders/sets found to export')
        save_scene(output.path, selection=True, force=force)

        _metadata = copy.deepcopy(metadata)
        _metadata['shd_yml'] = self.shd_yml.path
        output.set_metadata(_metadata)

    def _register_in_shotgrid(
            self, work, outs, upstream_files=None, link_textures=True):
        """Register outputs in shotgrid.

        Args:
            work (CPWork): source work file
            outs (CPOutput list): outputs that were generated
            upstream_files (list): list of upstream files
            link_textures (bool): register + link texture files in shotgrid
        """
        _upstream_files = upstream_files or []

        # Apply texture linking
        _link_textures = link_textures
        if os.environ.get('PINI_SG_DISABLE_REGISTER_TEX'):
            _link_textures = False
        if _link_textures:
            _upstream_files += _build_upstream_textures(
                paths=self.textures, work=work)

        super()._register_in_shotgrid(
            work=work, outs=outs, upstream_files=_upstream_files)


def _build_upstream_textures(paths, work=None):
    """Build upstream published files list.

    Used to link textures to publish in shotgrid.

    Args:
        paths (File list): upstream files
        work (CCPWork): work file

    Returns:
        (dict list): list of upstream published file entries
    """
    _LOGGER.info('BUILD UPSTREAM FILES')
    from pini.pipe import shotgrid

    _work = work or pipe.CACHE.obt_cur_work()
    _type = shotgrid.SGC.find_pub_type('Texture')
    _user = shotgrid.SGC.find_user(_work.owner())

    _to_pub = paths
    _up_pubs = []

    # Find already registered
    _rel_paths = {pipe.ROOT.rel_path(_path): _path for _path in paths}
    _filters = [('path_cache', 'in', list(_rel_paths.keys()))]
    for _pub in shotgrid.find(
            'PublishedFile', filters=_filters, fields=['path_cache']):
        _LOGGER.info(' - ALREADY PUBLISHED %s', _pub)
        _to_pub.remove(_rel_paths[_pub['path_cache']])
        _up_pubs.append(_pub)

    # Register remaining files
    for _path in qt.progress_bar(
            _to_pub, "Registering {:d} texture{}",
            stack_key='RegisterTextures'):
        if isinstance(_path, Seq):
            _thumb = TMP.to_file('pini/tmp.jpg')
            _path.build_thumbnail(_thumb, force=True)
        else:
            _thumb = _path
        _pub = shotgrid.create_pub_file_from_path(
            _path.path, type_=_type, task=_work.work_dir.sg_task, user=_user,
            ver_n=_work.ver_n, thumb=_thumb)
        _up_pubs.append(_pub)

    return _up_pubs


def _clean_junk():
    """Clean junk from current scene."""
    for _ref in ref.find_refs():  # Remove JUNK refs
        _top_node = _ref.find_top_node(catch=True)
        if (
                not _top_node or
                not to_long(_top_node).startswith('|JUNK|')):
            continue
        _LOGGER.info(' - REMOVE REF %s', _ref)
        _ref.delete(force=True)
    if cmds.objExists('JUNK'):
        cmds.delete('JUNK')


def _export_ass(metadata, force):
    """Export ass file of cache_SET geo.

    Args:
        metadata (dict): metadata to apply to ass file
        force (bool): overwrite existing without confirmation
    """
    _work = pipe.cur_work()

    # Find cache set
    _cache_set = single([
        _set for _set in cmds.ls(type='objectSet')
        if _set.endswith('cache_SET')], catch=True)
    if not _cache_set:
        _LOGGER.info(' - EXPORT ASS FAILED: MISSING CACHE SET')
        return None
    cmds.select(_cache_set)

    # Get ass path
    try:
        _ass = _work.to_output(
            'ass_gz', output_type='geo', output_name='shdCache')
    except ValueError:
        _LOGGER.info(' - NO ass_gz TEMPLATE FOUND IN %s', _work.job.name)
        return None

    # Export ass
    _ass.delete(wording='replace', force=force)
    assert not _ass.exists()
    _ass.test_dir()
    cmds.arnoldExportAss(
        filename=_ass.path,
        selected=True,
        shadowLinks=False,
        mask=6399,
        lightLinks=False,
        compressed=True,
        boundingBox=True,
        cam='perspShape')
    assert _ass.exists()

    # Apply metadata
    _data = copy.copy(metadata)
    for _key in ['shd_yml']:
        _data.pop(_key, None)
    _ass.set_metadata(_data)

    _LOGGER.info(' - EXPORTED ASS %s', _ass.path)

    return _ass


@disable_scanner_callbacks
def _flush_scene(keep_nodes=None):
    """Remove nodes from scene to prepare for lookdev export.

    Args:
        keep_nodes (list): list of nodes to keep in scene
    """
    _LOGGER.debug('FLUSH SCENE %s', keep_nodes)

    _keep_nodes = set(DEFAULT_NODES)
    if keep_nodes:
        _keep_nodes |= set(keep_nodes)

    # Import refs (NOTE: needs to happen before remove geos from sets
    # otherwise redshift sets get randomly deleted)
    _refs = ref.find_refs()
    _LOGGER.debug(' - REFS %s', _refs)
    for _ref in _refs:
        _LOGGER.debug('   - IMPORT REF %s', _ref)
        _ref.import_(namespace=None)

    # Remove geos from override sets
    _sets = lookdev.read_override_sets(crop_namespace=False)
    _LOGGER.debug(' - SETS %s', _sets)
    for _set, _geos in _sets.items():
        _keep_nodes.add(_set)
        _geos = sorted(set(_geos) - _keep_nodes)
        cmds.sets(_geos, remove=_set)
        _LOGGER.debug(' - CLEAN GEO %s set=%s', _geos, _set)

    # Move any lights in cache set into group
    _lights_grp = None
    _lights = m_pipe.read_cache_set(mode='lights')
    _LOGGER.debug(' - LIGHTS %s', _lights)
    for _light in _lights:
        _lights_grp = _light.add_to_grp('LIGHTS')
        _keep_nodes.add(_light)
        _keep_nodes.add(m_pipe.to_light_shp(_light))
    if _lights_grp:
        _lights_grp.parent(world=True)
        _lights_grp.set_outliner_col('Orange')
        _keep_nodes.add(_lights_grp)

    # Delete dag/unknown nodes
    _LOGGER.debug(' - KEEP NODES %s', _keep_nodes)
    _dag_nodes = [_node for _node in cmds.ls(dag=True)
                  if _node not in _keep_nodes]
    _LOGGER.debug(' - CLEARING DAG NODES %s', _dag_nodes)
    _unknown_nodes = cmds.ls(type='unknown') or []
    _LOGGER.debug(' - UNKNOWN NODES %s', _unknown_nodes)
    cmds.delete(_dag_nodes + _unknown_nodes)


def _read_textures(filter_=None):
    """Read textures from current scene.

    Args:
        filter_ (str): apply path filter (for debugging)

    Returns:
        (File list): textures
    """
    _ftns = set()
    for _file in pom.find_nodes('file'):
        _ftn = _file.plug['fileTextureName'].get_val()
        if not _ftn:
            continue
        _path = File(abs_path(_ftn))
        if filter_ and not passes_filter(_path.path, filter_):
            continue
        _LOGGER.debug('FILE %s', _file)
        _LOGGER.debug(' - FTN %s', _path)
        if _file.plug['uvTilingMode'].get_val():
            _LOGGER.debug(' - CONVERT TO SEQ')
            _path = to_seq(_path)
        if not _path.exists():
            continue
        _ftns.add(_path)
    return sorted(_ftns)
