"""Tools for managing the basic maya publish handler."""

import copy
import enum
import logging

from maya import cmds

from pini import pipe, dcc, qt
from pini.utils import single

from maya_pini import ref, open_maya as pom
from maya_pini.utils import (
    restore_sel, del_namespace, DEFAULT_NODES, save_abc, to_clean,
    save_fbx)

from . import phm_base

_LOGGER = logging.getLogger(__name__)
_PUB_REFS_MODE_KEY = 'PiniQt.Publish.References'


class PubRefsMode(enum.Enum):
    """Enum for managing how to handle references on publish."""

    REMOVE = "Remove"
    LEAVE_INTACT = "Leave intact"
    IMPORT_TO_ROOT = "Import into root namespace"


class CMayaBasicPublish(phm_base.CMayaBasePublish):
    """Manages a basic maya publish."""

    NAME = 'Maya Basic Publish'
    LABEL = '\n'.join([
        'Copies this scene to the publish directory.',
        '',
        ' - The top node should be GEO/RIG/MDL',
        ' - All the geometry should be added to a set named cache_SET',
        ' - Use JUNK group for nodes that should not get published',
        ' - For referenced geo, use the import references option',
        '',
        'You can use the sanity check tool to check your scene.',
    ])

    def build_ui(self, parent=None, layout=None, add_footer=True):
        """Build basic render interface into the given layout.

        Args:
            parent (QWidget): parent widget
            layout (QLayout): layout to add widgets to
            add_footer (bool): add footer elements
        """
        _LOGGER.debug('BUILD UI %s', self)
        super(CMayaBasicPublish, self).build_ui(
            parent=parent, layout=layout, add_footer=False)

        self.add_separator_elem()

        self.ui.RemoveJunk = self.add_checkbox_elem(
            val=True, name='RemoveJunk', label='Remove JUNK group')
        self.ui.RemoveSets = self.add_checkbox_elem(
            val=True, name='RemoveSets', label='Remove unused sets')
        self.ui.RemoveDLayers = self.add_checkbox_elem(
            val=True, name='RemoveDLayers', label='Remove display layers')
        self.add_separator_elem()

        self.ui.ExportAbc = self.add_checkbox_elem(
            val=True, name='ExportAbc',
            label="Export abc of cache_SET geo")
        self.ui.ExportFbx = self.add_checkbox_elem(
            val=False, name='ExportFbx',
            label="Export fbx of top node")
        self.add_separator_elem()

        # Add reference option
        _data = list(PubRefsMode)
        _items = [_item.value for _item in _data]
        self.ui.References = self.add_combobox_elem(
            name='References', items=_items, data=_data,
            save_policy=qt.SavePolicy.SAVE_IN_SCENE,
            settings_key=_PUB_REFS_MODE_KEY)
        self.add_separator_elem()

        # Add notes
        if add_footer:
            self.add_footer_elems()

        _LOGGER.debug(' - COMPLETED BUILD UI %s', self)

    @restore_sel
    def publish(
            self, work=None, force=False, revert=True, metadata=None,
            sanity_check_=True, export_abc=None, export_fbx=None,
            references=None, version_up=None):
        """Execute this publish.

        Args:
            work (CPWork): override work
            force (bool): force overwrite without confirmation
            revert (bool): revert to work file on completion
            metadata (dict): override metadata
            sanity_check_ (bool): apply sanity check
            export_abc (bool): whether to export rest cache abc
            export_fbx (bool): whether to export rest cache fbx
            references (str): how to handle references (eg. Remove)
            version_up (bool): whether to version up on publish

        Returns:
            (CPOutput): publish file
        """
        _LOGGER.info('PUBLISH force=%d', force)

        # Force refs mode to write scene data for sanity check
        if self.ui_is_active():
            self.ui.References.currentTextChanged.emit(
                self.ui.References.currentText())

        # Read options/outputs
        _work = work or pipe.CACHE.cur_work
        _metadata = metadata or self.build_metadata(
            work=_work, force=force, sanity_check_=sanity_check_)
        _LOGGER.info(' - OBTAINED METADATA %s', _metadata)
        _pub = _work.to_output('publish', output_type=None, extn='ma')
        _LOGGER.info(' - OUTPUT %s', _pub.path)

        if self.ui_is_active():
            self.ui.save_settings()
        _pub.delete(wording='Replace', force=force)
        _work.save(reason='publish', force=True, update_outputs=False)

        self._clean_scene(references=references)

        # Save publish
        dcc.save(_pub)
        _outs = [_pub]
        _pub.set_metadata(_metadata)

        # Export versionless
        _pub_vl = self.create_versionless(
            work=_work, publish=_pub, metadata=_metadata)
        if _pub_vl:
            _outs.append(_pub_vl)

        # Export abc
        _export_abc = export_abc
        if _export_abc is None and self.ui_is_active():
            _export_abc = self.ui.ExportAbc.isChecked()
        if _export_abc is None:
            _export_abc = True
        if _export_abc:
            _abc = _exec_export_abc(work=_work, metadata=_metadata, force=force)
            if _abc:
                _outs.append(_abc)

        # Export fbx
        _export_fbx = export_fbx
        if _export_fbx is None and self.ui_is_active():
            _export_fbx = self.ui.ExportFbx.isChecked()
        if _export_fbx:
            _fbx = _exec_export_fbx(work=_work, metadata=_metadata, force=force)
            if _fbx:
                _outs.append(_fbx)

        if revert:
            _work.load(force=True)

        self.post_publish(work=_work, outs=_outs, version_up=version_up)

        return _outs

    def _clean_scene(self, references=None):
        """Apply clean scene options to prepare for publish.

        Args:
            references (str): how to handle references (eg. Remove)
        """
        _remove_junk = (
            self.ui.RemoveJunk.isChecked() if self.ui_is_active() else True)
        _remove_sets = (
            self.ui.RemoveSets.isChecked() if self.ui_is_active() else True)
        _remove_dlayers = (
            self.ui.RemoveDLayers.isChecked() if self.ui_is_active() else True)

        # Apply reference option
        _refs = references
        if _refs is None and self.ui:
            _refs = self.ui.References.currentText()
        if _refs is None:
            _refs = 'Remove'
        _LOGGER.info(' - REFS OPT %s', _refs)
        if _refs == 'Remove':
            for _ref in ref.find_refs():
                _ref.delete(force=True, delete_foster_parent=True)
        elif _refs == 'Leave intact':
            pass
        elif _refs == 'Import into root namespace':
            for _ref in ref.find_refs():
                _LOGGER.info(' - IMPORT REF %s', _ref)
                _ns = _ref.namespace  # Need to read before import
                _ref.import_()
                cmds.namespace(moveNamespace=(_ns, ':'), force=True)
                del_namespace(_ns, force=True)
        else:
            raise ValueError(_refs)

        # Remove JUNK
        if _remove_junk and cmds.objExists('JUNK'):
            cmds.delete('JUNK')

        # Remove unused sets
        if _remove_sets:
            _sets = _find_dag_sets()
            _keep_sets = ('cache_SET', 'ctrls_SET')
            _to_delete = [
                _set for _set in _sets
                if _set not in _keep_sets and
                not cmds.referenceQuery(_set, isNodeReferenced=True) and
                _set not in DEFAULT_NODES]
            _LOGGER.info(' - CLEAN SETS %s', _to_delete)
            if _to_delete:
                cmds.delete(_to_delete)

        # Flush display layers
        if _remove_dlayers:
            _lyrs = pom.find_nodes(
                type_='displayLayer', referenced=False, default=False)
            cmds.delete(_lyrs)


def _exec_export_abc(work, metadata, force=False):
    """Save restCache abc.

    Args:
        work (CPWork): work file
        metadata (dict): publish metadata
        force (bool): overwrite existing without confirmation

    Returns:
        (CPOutput): abc
    """

    # Make sure we can cache
    if not cmds.objExists('cache_SET'):
        _LOGGER.info(' - UNABLE TO EXPORT ABC - MISSING cache_SET')
        return None
    _tmpl = work.find_template('cache', catch=True)
    if not _tmpl:
        _LOGGER.info(' - UNABLE TO EXPORT ABC - NO CACHE TEMPLATE %s', work)
        return None

    # Save abc
    _abc = work.to_output(
        _tmpl, output_type='geo', output_name='restCache', extn='abc')
    _LOGGER.info(' - REST CACHE ABC %s', _abc)
    _geo = cmds.sets('cache_SET', query=True)
    if not _geo:
        _LOGGER.info(' - UNABLE TO EXPORT ABC - EMPTY cache_SET')
        return None
    _frame = int(cmds.currentTime(query=True))
    _rng = (_frame, _frame)
    save_abc(abc=_abc, range_=_rng, geo=_geo, force=force)
    _LOGGER.info(' - SAVED ABC %s', _abc.path)

    # Save metadata
    _data = copy.copy(metadata)
    _data['range'] = (_frame, )
    _abc.set_metadata(_data)

    return _abc


def _exec_export_fbx(work, metadata, constraints=True, force=False):
    """Save restCache fbx.

    Args:
        work (CPWork): work file
        metadata (dict): publish metadata
        constraints (bool): export constraints
        force (bool): overwrite existing without confimation

    Returns:
        (CPOutput): fbx
    """
    _LOGGER.debug('EXPORT FBX')

    # Find top node
    _top_node = _find_top_node()
    if not _top_node:
        _LOGGER.info(' - UNABLE TO EXPORT FBX - NO TOP NODE FOUND')
        return None
    _tmpl = work.find_template('cache', catch=True)
    if not _tmpl:
        _LOGGER.info(' - UNABLE TO EXPORT ABC - NO CACHE TEMPLATE %s', work)
        return None
    cmds.select(_top_node)
    _LOGGER.debug(' - TOP NODE %s', _top_node)

    # Get fbx path
    _fbx = work.to_output(
        _tmpl, output_type='fbx', extn='fbx', output_name='restCache')
    _fbx.delete(wording='Replace', force=force)
    _LOGGER.debug(' - FBX %s', _fbx.path)

    # Export fbx
    save_fbx(_fbx, constraints=constraints, selection=True)

    _fbx.set_metadata(metadata)

    return _fbx


def _find_top_node():
    """Find current scene top node.

    Returns:
        (str): top node (eg. MDL/RIG)
    """
    return single([
        to_clean(_node) for _node in cmds.ls(long=True, dagObjects=True)
        if _node.count('|') == 1 and
        to_clean(_node) not in DEFAULT_NODES], catch=True)


def _is_deform_set(set_):
    """Test if the given set is a deformation set.

    It seems like sometimes the listSets command fails to identify deformation
    sets, so this manually recreates that functionaily.

    Args:
        set_ (str): set to check

    Returns:
        (bool): whether deformation set
    """
    _conns = cmds.listConnections(set_) or []
    _types = {cmds.objectType(_item) for _item in _conns}
    _dfm_types = {'cluster', 'tweak', 'blendShape', 'groupId'}
    return bool(_dfm_types & _types)


def _find_dag_sets():
    """Find sets in the outliner in the current scene.

    Returns:
        (CNode list): sets
    """
    _sets = set(pom.CMDS.ls(type='objectSet'))
    _sets -= set(cmds.listSets(type=1) or [])  # Remove render sets
    _sets -= set(cmds.listSets(type=2) or [])  # Remove deform sets
    _sets = [_set for _set in sorted(_sets)
             if _set.object_type() == 'objectSet' and
             not _is_deform_set(_set)]
    return _sets


def get_pub_refs_mode():
    """Obtain current publish references mode setting.

    Returns:
        (PubRefsMode): current references mode
    """
    _LOGGER.debug('GET PUB REFS MODE')
    _mode = None
    _scn = dcc.get_scene_data(_PUB_REFS_MODE_KEY)
    _LOGGER.debug(' - VAL %s %s', _scn, _PUB_REFS_MODE_KEY)
    if _scn:
        _mode = single(
            [_item for _item in list(PubRefsMode) if _item.value == _scn],
            catch=True)
        _LOGGER.debug(' - MATCHED %s', _mode)

    return _mode or PubRefsMode.REMOVE


def set_pub_refs_mode(mode):
    """Set current publish references mode.

    Args:
        mode (PubRefsMode): mode to apply
    """
    _LOGGER.info('SET PUB REFS MODE %s', mode)
    assert isinstance(mode, PubRefsMode)

    _LOGGER.info(' - VAL STR %s', mode.value)

    for _handler in dcc.find_export_handlers('Publish'):
        if not _handler.ui_is_active():
            continue
        if not hasattr(_handler.ui, 'References'):
            continue
        _handler.ui.References.setCurrentText(mode.value)

    dcc.set_scene_data(_PUB_REFS_MODE_KEY, mode.value)
