"""Tools for managing maya publish handlers."""

import copy
import logging

from maya import cmds

from pini import pipe
from pini.utils import single

from maya_pini import ref
from maya_pini.m_pipe import lookdev
from maya_pini.utils import (
    restore_sel, DEFAULT_NODES, to_long, to_namespace)

from .. import ph_basic

_LOGGER = logging.getLogger(__name__)


class CMayaLookdevPublish(ph_basic.CBasicPublish):
    """Manages a maya lookdev publish."""

    NAME = 'Maya Lookdev Publish'
    LABEL = '\n'.join([
        ' - Builds lookdev files for abc attach'
        ' - Nodes in JUNK group are ignored'
        ' - Any sets in overrides_SET are saved and restored on abc attach'
    ])

    shd_yml = None

    def build_ui(self, parent=None, layout=None, add_notes=True):
        """Build basic render interface into the given layout.

        Args:
            parent (QWidget): parent widget
            layout (QLayout): layout to add widgets to
            add_notes (bool): add notes element
        """
        super(CMayaLookdevPublish, self).build_ui(
            parent=parent, layout=layout, add_notes=False)

        self.add_separator_elem()
        self.ui.ExportAss = self.add_checkbox_elem(
            val=True, name='ExportAss',
            label="Export geo as ass.gz file")
        self.add_separator_elem()
        if add_notes:
            self.add_notes_elem()

    def obtain_metadata(self, work=None, sanity_check_=True, force=False):
        """Obtain publish metadata.

        Args:
            work (CPWork): override workfile to read metadata from
            sanity_check_ (bool): run sanity checks before publish
            force (bool): force completion without any confirmations

        Returns:
            (dict): metadata
        """
        _data = super(CMayaLookdevPublish, self).obtain_metadata(
            work=work, sanity_check_=sanity_check_, force=force)
        del _data['range']
        if self.shd_yml:
            _data['shd_yml'] = self.shd_yml.path
        return _data

    @restore_sel
    def publish(self, work=None, force=False):
        """Execute lookdev publish.

        Args:
            work (CPWork): override publish work file
            force (bool): force overwrite without confirmation

        Returns:
            (CPOutput): publish file
        """
        _LOGGER.info('LOOKDEV PUBLISH')

        _work = work or pipe.cur_work()
        _pub = _work.to_output('publish', output_type='lookdev')
        _data_dir = _pub.to_dir().to_subdir('data')
        self.shd_yml = _pub.to_file(
            dir_=_data_dir,  base=_pub.base+'_shaders', extn='yml')

        _LOGGER.info(' - SHD YML %s', self.shd_yml)

        _metadata = self.obtain_metadata(force=force)
        _work.save(reason='lookdev publish', force=True)

        # Check scene
        _clean_junk()
        _assignments = lookdev.read_shader_assignments()
        if not _assignments:
            if lookdev.read_shader_assignments(allow_referenced=True):
                raise RuntimeError('Referenced shaders are not supported')
            raise RuntimeError('No valid shading assignments found')
        for _shd in _assignments:
            if to_namespace(_shd):
                raise RuntimeError('Shader has namespace '+_shd)

        # Export ass
        _tgl_export_ass = self.ui.ExportAss.isChecked() if self.ui else True
        if _tgl_export_ass:
            _export_ass(metadata=_metadata, force=force)

        # Read shaders + save to yml
        _shd_data = lookdev.read_publish_metadata()
        self.shd_yml.write_yml(_shd_data, force=True, fix_unicode=True)
        _LOGGER.info(' - WROTE SHD YML %s', self.shd_yml)

        # Export shaders mb
        _export_nodes = _find_export_nodes()
        _flush_scene()
        _export_nodes = [  # Empty sets are deleted on import ref (?)
            _node for _node in _export_nodes if cmds.objExists(_node)]
        cmds.select(_export_nodes, noExpand=True)
        if not _export_nodes:
            raise RuntimeError('No shaders/sets found to export')
        _type = {'ma': 'mayaAscii', 'mb': 'mayaBinary'}[_pub.extn]
        cmds.file(_pub.path, exportSelected=True, type=_type, force=True)
        _pub.set_metadata(_metadata)
        _work.load(force=True)

        self.post_publish(work=_work, outs=[_pub])

        return _pub


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
        return
    cmds.select(_cache_set)

    # Get ass path
    try:
        _ass = _work.to_output(
            'ass_gz', output_type='geo', output_name='shdCache')
    except ValueError:
        _LOGGER.info(' - NO ass_gz TEMPLATE FOUND IN %s', _work.job.name)
        return

    # Export ass
    _ass.delete(wording='Replace', force=force)
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


def _find_export_nodes():
    """Find nodes to export in lookdev mb file.

    Returns:
        (str list): lookdev nodes
    """
    _export_nodes = set()

    # Add shaders
    for _shd, _data in lookdev.read_shader_assignments().items():
        _export_nodes.add(_shd)
        _export_nodes.add(_data['shadingEngine'])

    # Add override sets
    if cmds.objExists('overrides_SET'):
        _export_nodes.add('overrides_SET')
    for _set, _ in lookdev.read_ai_override_sets().items():
        _export_nodes.add(_set)

    _export_nodes = sorted(_export_nodes)
    _LOGGER.info(' - EXPORT NODES %s', _export_nodes)

    return sorted(_export_nodes)


def _flush_scene():
    """Remove geo from scene to prepare for lookdev export."""
    _LOGGER.debug('FLUSH SCENE')

    # Remove geos from override sets
    _sets = lookdev.read_ai_override_sets(crop_namespace=False)
    _LOGGER.debug(' - SETS %s', _sets)
    for _set, _geos in _sets.items():
        cmds.sets(_geos, remove=_set)
        _LOGGER.debug(' - CLEAN GEO %s set=%s', _geos, _set)

    # Delete dag/unknown nodes
    _refs = ref.find_refs()
    _LOGGER.debug(' - REFS %s', _refs)
    for _ref in _refs:
        _ref.import_()
    _dag_nodes = [_node for _node in cmds.ls(dag=True)
                  if _node not in DEFAULT_NODES]
    _LOGGER.debug(' - CLEARING DAG NODES %s', _dag_nodes)
    _unknown_nodes = cmds.ls(type='unknown') or []
    _LOGGER.debug(' - UNKNOWN NODES %s', _unknown_nodes)
    cmds.delete(_dag_nodes + _unknown_nodes)
