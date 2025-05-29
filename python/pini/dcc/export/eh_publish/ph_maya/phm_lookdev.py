"""Tools for managing maya publish handlers."""

import logging
import os

from maya import cmds

from pini import pipe, dcc, qt, icons
from pini.utils import File, abs_path, passes_filter, to_seq, Seq, TMP

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
    ACTION = 'LookdevPublish'
    ICON = icons.find('Palette')
    COL = 'Gold'
    TYPE = 'Publish'

    LABEL = '\n'.join([
        'Builds lookdev files for abc attach. Shaders should be built on '
        'a reference of the model or rig.',
        '',
        ' - Shaders are stored in maya file and attached using yml',
        ' - Any sets in overrides_SET are saved and restored on abc attach',
        ' - Nodes in JUNK group are ignored',
        ' - Any lights found in the model/rig are saved and attached '
        'to the matching transform on to the abc',
    ])

    shd_yml = None
    textures = None

    def _add_custom_ui_elems(self):
        """Add custom ui elements."""
        self._add_pxy_opts()

    def _add_pxy_opts(self):
        """Build proxy publish options."""
        _ass = 'arnold' in dcc.allowed_renderers()
        _vrm = 'vray' in dcc.allowed_renderers()
        _rs = 'redshift' in dcc.allowed_renderers()

        if not (_ass or _vrm or _rs):
            return

        self.ui.add_separator()
        if _ass:
            self.ui.add_check_box(
                val=True, name='Ass',
                label="Export ass.gz of geo")
        if _vrm:
            self.ui.add_check_box(
                val=True, name='VrmMa',
                label="Export shaded vrmesh scene of geo")
        if _rs:
            self.ui.add_check_box(
                val=True, name='RsPxy',
                label="Export redshift proxy of geo")
        if _vrm or _rs:
            self.ui.add_check_box(
                val=False, name='PxyAnim',
                label='Include animation in proxies')

        # self.ui.add_separator()

    def build_metadata(self):
        """Build publish metadata.

        Returns:
            (dict): metadata
        """
        _data = super().build_metadata()
        del _data['range']
        return _data

    @restore_sel
    def export(  # pylint: disable=unused-argument
            self, notes=None, version_up=None, snapshot=True, bkp=True,
            progress=True, ass=False, vrm_ma=False, rs_pxy=False,
            pxy_anim=False, force=False):
        """Execute lookdev publish.

        Args:
            notes (str): export notes
            version_up (bool): version up after export
            snapshot (bool): take thumbnail snapshot on export
            bkp (bool): save bkp file
            progress (bool): show progress bar
            ass (bool): export ass file
            vrm_ma (bool): export vrmesh ma file
            rs_pxy (bool): export redshift proxy
            pxy_anim (bool): include anim in proxies
            force (bool): force overwrite without confirmation

        Returns:
            (CPOutput): publish file
        """
        _LOGGER.info('LOOKDEV PUBLISH')

        # Setup output attrs
        self.publish = self.work.to_output(
            'publish', output_type='lookdev', extn='ma')
        _data_dir = self.publish.to_dir().to_subdir('data')
        self.shd_yml = self.publish.to_file(
            dir_=_data_dir, base=self.publish.base + '_shaders', extn='yml')
        _LOGGER.info(' - SHD YML %s', self.shd_yml)
        self.outputs = []

        # Check scene
        self.progress.set_pc(15)
        _clean_junk()
        _assignments = lookdev.read_shader_assignments(referenced=False)
        if not _assignments:
            if lookdev.read_shader_assignments(referenced=True):
                raise RuntimeError('Referenced shaders are not supported')
            raise RuntimeError('No valid shading assignments found')
        for _shd in _assignments:
            if to_namespace(_shd):
                raise RuntimeError('Shader has namespace ' + _shd)
        self.textures = _read_textures()
        self.progress.set_pc(20)

        # Generate outputs
        _LOGGER.debug(' - GENERATE ASS %s', self.outputs)
        self._handle_export_ass()
        self.progress.set_pc(30)

        # Export vrmesh ma
        _LOGGER.debug(' - GENERATE VRM MA %s', self.outputs)
        self._handle_export_vrm_ma()
        self.progress.set_pc(40)

        # Export redshift proxy
        _LOGGER.debug(' - GENERATE RS PROXY %s', self.outputs)
        self._handle_export_rs_pxy()
        self.progress.set_pc(50)

        # Export shaders ma
        _LOGGER.debug(' - GENERATE SHADERS %s', self.outputs)
        self._handle_export_shaders_scene()
        self.progress.set_pc(60)
        assert self.publish in self.outputs

        self.progress.set_pc(80)
        self.work.load(force=True)
        _LOGGER.debug(' - COMPLETE %s', self.outputs)

    def _handle_export_ass(self):
        """Handle export ass file."""
        _force = self.settings['force']
        _ass = self.settings['ass']
        if not _ass:
            return
        _ass_out = _export_ass(force=_force)
        self.outputs.append(_ass_out)

    def _handle_export_vrm_ma(self):
        """Handle export vray mesh ma file."""
        _force = self.settings['force']
        _export_vrm_ma = self.settings['vrm_ma']
        _anim = self.settings['pxy_anim']
        if not _export_vrm_ma:
            return
        _vrm = lookdev.export_vrmesh_ma(force=_force, animation=_anim)
        if not _vrm:
            return
        self.outputs.append(_vrm)

    def _handle_export_rs_pxy(self):
        """Handle export redshift proxy file."""
        _force = self.settings['force']
        _export_rs_pxy = self.settings['rs_pxy']
        _anim = self.settings['pxy_anim']
        if not _export_rs_pxy:
            return

        _tmpl = 'publish' if not _anim else 'publish_seq'
        _rs_pxy = self.work.to_output(
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
                _rs_pxy, selection=True, animation=_anim, force=_force)
        except RuntimeError as _exc:
            _LOGGER.error('FAILED TO EXPORT REDSHIFT PROXY %s', _exc)
            return
        _rs_pxy.add_metadata(animated=_anim)
        self.outputs.append(_rs_pxy)

    def _handle_export_shaders_scene(self):
        """Handle export shaders ma file."""
        _force = self.settings['force']

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
        save_scene(self.publish.path, selection=True, force=_force)

        self.publish.add_metadata(shd_yml=self.shd_yml.path)
        self.outputs.append(self.publish)

    def _register_in_shotgrid(self, upstream_files=None, link_textures=True):
        """Register outputs in shotgrid.

        Args:
            upstream_files (list): list of upstream files
            link_textures (bool): register + link texture files in shotgrid
        """
        _upstream_files = upstream_files or []

        # Apply texture linking
        _link_textures = link_textures
        if os.environ.get('PINI_SG_DISABLE_REGISTER_TEX'):
            _link_textures = False
        if _link_textures and self.textures:
            _upstream_files += _build_upstream_textures(
                paths=self.textures, work=self.work)

        super()._register_in_shotgrid(upstream_files=_upstream_files)


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
    _LOGGER.info(' - FILTERS %s', _filters)
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


def _export_ass(force):
    """Export ass file of cache_SET geo.

    Args:
        force (bool): overwrite existing without confirmation
    """
    _work = pipe.cur_work()

    # Find cache set
    _cache_set = m_pipe.find_cache_set()
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
        _udims = _file.plug['uvTilingMode'].get_val()
        _LOGGER.debug(' - UDIMS %s', _udims)
        if _udims:
            _path = _path.replace('<UDIM>', '%04d')
            _path = _path.replace('1001.', '%04d.')
            _LOGGER.debug(' - CONVERT TO SEQ %s', _path)
            _path = to_seq(_path, safe=False)
            _LOGGER.debug(' - FTN %s', _path)
        if not _path or not _path.exists():
            _LOGGER.debug(' - REJECTED %s', _path)
            continue
        _ftns.add(_path)
    return sorted(_ftns)
