"""Tools for managing the basic maya publish handler."""

import enum
import logging
import os

from maya import cmds

from pini import dcc, icons
from pini.utils import single

from maya_pini import open_maya as pom, m_pipe
from maya_pini.utils import (
    restore_sel, del_namespace, DEFAULT_NODES, save_abc, to_clean,
    save_fbx)

from .. import ph_basic

_LOGGER = logging.getLogger(__name__)
_PUB_REFS_MODE_KEY = 'PiniQt.Publish.References'


class PubRefsMode(enum.Enum):
    """Enum for managing how to handle references on publish."""

    REMOVE = "Remove"
    LEAVE_INTACT = "Leave intact"
    IMPORT_TO_ROOT = "Import into root namespace"
    IMPORT_USING_UNDERSCORES = "Import replacing namespaces with underscores"


def _to_default_pub_ref_mode():
    """Read default publish references mode.

    Returns:
        (PubRefsMode): default value
    """
    if 'PINI_PUB_REFS_MODE' in os.environ:
        _name = os.environ['PINI_PUB_REFS_MODE']
        _match = single([
            _item for _item in PubRefsMode if _item == _name],
            catch=True)
        if _match:
            return _match
    return PubRefsMode.REMOVE


_PUB_REFS_DEFAULT = _to_default_pub_ref_mode()


class CMayaBasicPublish(ph_basic.CBasicPublish):
    """Manages a basic maya publish."""

    NAME = 'Maya Basic Publish'
    ICON = icons.find('Beer Mug')
    COL = 'Salmon'
    TYPE = 'Publish'

    LABEL = '\n'.join([
        'Copies this scene to the publish directory - this is generally '
        'used to pass a rig/model/lookdev asset down the pipeline for '
        'use in shots.',
        '',
        'Here are some tips:',
        '',
        ' - The top node should be GEO/RIG/MDL',
        ' - All the geometry should be added to a set named cache_SET',
        ' - Use JUNK group for nodes that should not get published',
        ' - For referenced geo, use the import references option',
        '',
        'You can use the sanity check tool to check your scene.',
    ])

    def _add_custom_ui_elems(self):
        """Add custom ui elements."""
        self.ui.add_separator()

        self.ui.add_check_box(
            val=True, name='RemoveJunk', label='Remove JUNK group')
        self.ui.add_check_box(
            val=True, name='RemoveSets', label='Remove unused sets')
        self.ui.add_check_box(
            val=True, name='RemoveDlayers', label='Remove display layers')
        self.ui.add_check_box(
            val=True, name='RemoveAlayers', label='Remove anim layers')
        self.ui.add_separator()

        self.ui.add_check_box(
            val=True, name='Abc',
            label="Export abc of cache_SET geo")
        self.ui.add_check_box(
            val=False, name='Fbx',
            label="Export fbx of top node")
        self.ui.add_separator()

        # Add reference option
        _data = list(PubRefsMode)
        _items = [_item.value for _item in _data]
        _val = dcc.get_scene_data(_PUB_REFS_MODE_KEY) or _PUB_REFS_DEFAULT.value
        self.ui.add_combo_box(
            name='References', items=_items, data=_data,
            val=_val, settings_key=_PUB_REFS_MODE_KEY)
        self.ui.add_label(
            name='ReferencesLabel', text=' - Blah blah blah', add_layout=True)
        self._callback__References()

    def _callback__References(self):
        _LOGGER.debug('CALLBACK References')
        _refs_mode_s = self.ui.References.selected_text()
        _LOGGER.debug(' - REFS MODE %s', _refs_mode_s)
        _refs_mode = PubRefsMode(_refs_mode_s)
        _label = {
            PubRefsMode.REMOVE: ' - Removes all references from the scene',
            PubRefsMode.LEAVE_INTACT: '\n'.join([
                ' - Leaves references in the scene as they are in the publish',
                ' - This may cause abc export issues']),
            PubRefsMode.IMPORT_TO_ROOT: '\n'.join([
                ' - Imports references, removing their namespaces',
                ' - Use this if you are referencing your model geo']),
            PubRefsMode.IMPORT_USING_UNDERSCORES: '\n'.join([
                ' - Imports references, replacing namespace for underscores',
                ' - Makes sure each node has a unique name for abc export',
                ' - Use if your model geo uses more than one reference']),
        }[_refs_mode]
        self.ui.ReferencesLabel.setText(_label)

    def exec_from_ui(self, **kwargs):
        """Execuate this export using settings from ui.

        Args:
            kwargs (dict): override exec kwargs
        """

        # Force references elem to save
        self.ui.References.currentTextChanged.emit(
            self.ui.References.currentText())

        return super().exec_from_ui(**kwargs)

    @restore_sel
    def export(  # pylint: disable=unused-argument
            self, notes=None, version_up=True, snapshot=True, save=True,
            bkp=True, progress=True, update_metadata=True, update_cache=True,
            abc=False, fbx=False, references=None, remove_alayers=True,
            remove_dlayers=True, remove_junk=True, remove_sets=True,
            work=None, force=False):
        """Execute this publish.

        Args:
            notes (str): export notes
            version_up (bool): version up after export
            snapshot (bool): take thumbnail snapshot on export
            save (bool): save work file on export
            bkp (bool): save bkp file
            progress (bool): show progress bar
            update_metadata (bool): update output metadata
            update_cache (bool): update pipe cache
            abc (bool): whether to export rest cache abc
            fbx (bool): whether to export rest cache fbx
            references (str): how to handle references (eg. Remove)
            remove_alayers (bool): remove anim layers
            remove_dlayers (bool): remove display layers
            remove_junk (bool): remove JUNK group
            remove_sets (bool): remove unused sets
            work (CPWork): override work file (for testing)
            force (bool): force overwrite without confirmation

        Returns:
            (CPOutput): publish file
        """
        _LOGGER.info('EXEC %s force=%d', self, force)

        _pub = self.work.to_output('publish', output_type=None, extn='ma')
        _pub.delete(wording='replace', force=force)

        self._clean_scene()
        self.progress.set_pc(30)

        # Save main publish file
        _LOGGER.info(' - OUTPUT %s', _pub.path)
        dcc.save(_pub)
        self.outputs = [_pub]
        self.progress.set_pc(60)

        # Export abc
        if abc:
            _abc = _exec_export_abc(work=self.work, force=force)
            if _abc:
                self.outputs.append(_abc)
        self.progress.set_pc(70)

        # Export fbx
        if fbx:
            _fbx = _exec_export_fbx(work=self.work, force=force)
            if _fbx:
                self.outputs.append(_fbx)

        # Revert scene
        self.progress.set_pc(75)
        self.work.load(force=True)
        self.progress.set_pc(85)

        return self.outputs

    def _clean_scene(self):
        """Apply clean scene options to prepare for publish.
        """
        _LOGGER.debug('CLEAN SCENE')
        _remove_junk = self.settings['remove_junk']
        _remove_sets = self.settings['remove_sets']
        _remove_dlayers = self.settings['remove_dlayers']
        _remove_alayers = self.settings['remove_alayers']

        _apply_refs_mode_opt(refs_mode=self.settings['references'])

        # Remove JUNK
        _LOGGER.debug(' - APPLY REMOVE JUNK %d', _remove_junk)
        if _remove_junk and cmds.objExists('JUNK'):
            _remove_junk_refs()
            cmds.delete('JUNK')

        # Remove unused sets
        if _remove_sets:
            _sets = _find_dag_sets()
            _keep_sets = ('cache_SET', m_pipe.find_ctrls_set(mode='name'))
            _LOGGER.debug(' - KEEP SETS %s', _keep_sets)
            _to_delete = [
                _set for _set in _sets
                if _set not in _keep_sets and
                not cmds.referenceQuery(_set, isNodeReferenced=True) and
                _set not in DEFAULT_NODES]
            _LOGGER.debug(' - CLEAN SETS %s', _to_delete)
            if _to_delete:
                cmds.delete(_to_delete)

        # Flush display layers
        if _remove_dlayers:
            _lyrs = pom.find_nodes(
                type_='displayLayer', referenced=False, default=False)
            cmds.delete(_lyrs)

        if _remove_alayers:
            cmds.delete(cmds.ls(type='animLayer'))


def _apply_refs_mode_opt(refs_mode):
    """Apply references mode option.

    Args:
        refs_mode (PubRefsMode): references mode
    """
    _LOGGER.debug('APPLY REF OPTS')

    # Determine refs mode
    _refs_mode = refs_mode
    if not _refs_mode:
        _refs_mode = dcc.get_scene_data(_PUB_REFS_MODE_KEY)
        _LOGGER.debug(' - READ SCENE DATA %s', _PUB_REFS_MODE_KEY)
    if not _refs_mode:
        _refs_mode = _PUB_REFS_DEFAULT.value
    _LOGGER.info(' - REFS OPT %s', _refs_mode)

    # Apply reference option
    _refs = pom.find_refs(allow_no_namespace=True)
    if _refs_mode == 'Remove':
        for _ref in _refs:
            _ref.delete(force=True, delete_foster_parent=True)
    elif _refs_mode in ('Leave intact', 'No action'):
        pass
    elif _refs_mode.startswith('Import '):
        _import_refs(refs_mode=_refs_mode, refs=_refs)
    else:
        raise ValueError(_refs_mode)


def _import_refs(refs_mode, refs):
    """Import references.

    Args:
        refs_mode (PubRefsMode): references mode
        refs (CReference list): references
    """
    for _ref in refs:

        # Delete JUNK refs
        if (
                _ref.top_node and
                _ref.top_node.to_long().startswith('|JUNK')):
            _ref.delete(force=True)
            continue

        # Apply import
        _LOGGER.info(' - IMPORT REF %s', _ref)
        _ns = _ref.namespace  # Need to read before import
        _nodes = _ref.find_nodes(dag_only=True)
        _ref.import_()

        # Apply refs mode
        if refs_mode == 'Import into root namespace':
            cmds.namespace(moveNamespace=(_ns, ':'), force=True)
            del_namespace(_ns, force=True)
        elif refs_mode == 'Import replacing namespaces with underscores':
            for _node in _nodes:
                _node.rename(str(_node).replace(':', '_'))
        else:
            raise ValueError(refs_mode)


def _exec_export_abc(work, force=False):
    """Save restCache abc.

    Args:
        work (CPWork): work file
        force (bool): overwrite existing without confirmation

    Returns:
        (CPOutput): abc
    """

    # Make sure we can cache
    _cache_set = m_pipe.find_cache_set()
    if not _cache_set:
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
    _geo = m_pipe.read_cache_set(set_=_cache_set, mode='top')
    if not _geo:
        _LOGGER.info(' - UNABLE TO EXPORT ABC - EMPTY cache_SET')
        return None
    _frame = int(cmds.currentTime(query=True))
    _rng = _frame, _frame
    save_abc(abc=_abc, range_=_rng, geo=_geo, force=force)
    _LOGGER.info(' - SAVED ABC %s', _abc.path)

    return _abc


def _exec_export_fbx(work, constraints=True, force=False):
    """Save restCache fbx.

    Args:
        work (CPWork): work file
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
    _fbx.delete(wording='replace', force=force)
    _LOGGER.debug(' - FBX %s', _fbx.path)

    # Export fbx
    save_fbx(_fbx, constraints=constraints, selection=True)

    return _fbx


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


def _find_top_node():
    """Find current scene top node.

    Returns:
        (str): top node (eg. MDL/RIG)
    """
    return single([
        to_clean(_node) for _node in cmds.ls(long=True, dagObjects=True)
        if _node.count('|') == 1 and
        to_clean(_node) not in DEFAULT_NODES], catch=True)


def get_pub_refs_mode():
    """Obtain current publish references mode setting.

    Returns:
        (PubRefsMode): current references mode
    """
    _LOGGER.log(9, 'GET PUB REFS MODE')
    _mode = None
    _scn = dcc.get_scene_data(_PUB_REFS_MODE_KEY)
    _LOGGER.log(9, ' - VAL %s %s', _scn, _PUB_REFS_MODE_KEY)
    if _scn:
        _mode = single(
            [_item for _item in list(PubRefsMode) if _item.value == _scn],
            catch=True)
        _LOGGER.log(9, ' - MATCHED %s', _mode)

    return _mode or PubRefsMode.REMOVE


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


def _remove_junk_refs():
    """Remove references in JUNK group."""
    for _ref in pom.find_refs():
        _grp = single(
            {_node.to_parent() for _node in _ref.top_nodes},
            catch=True)
        if _grp == 'JUNK':
            _ref.delete(force=True)


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
