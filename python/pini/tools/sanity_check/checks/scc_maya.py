"""Maya specific sanity checks."""

import collections
import logging
import os
import platform
import re

from maya import cmds

from pini import qt, dcc, pipe
from pini.utils import (
    single, wrap_fn, check_heart, nice_size, cache_result, Path,
    abs_path, Dir)

from maya_pini import ref, open_maya as pom, m_pipe
from maya_pini.utils import DEFAULT_NODES, to_clean

from .. import core, utils

_LOGGER = logging.getLogger(__name__)


class CheckUnmappedPaths(core.SCMayaCheck):
    """Check for unmapped reference paths.

    These are maps which have been set up on another OS, which can
    be updated using the pipe.map_path function.
    """

    sort = 40

    def run(self):
        """Execute this check."""
        _refs = ref.find_path_refs()
        for _ref in _refs:

            self.write_log('Checking ref %s', _ref)

            _cur_path = Path(_ref.path)
            self.write_log(' - cur path %s', _cur_path.path)
            _map_path = Path(pipe.map_path(_ref.path))
            self.write_log(' - map path %s', _map_path.path)

            if _cur_path != _map_path:

                # Find node
                if isinstance(_ref, ref.FileRef):
                    _node = _ref.find_top_node(catch=True) or _ref.ref_node
                    _is_file = True
                    _name = _ref.namespace
                elif isinstance(_ref, ref.AttrRef):
                    _node = _ref.node
                    _is_file = False
                    _name = _node
                else:
                    raise ValueError

                # Check map path exists
                if _is_file and not _map_path.exists():
                    _msg = (
                        'Reference {} has a path which can be updated for '
                        '{} but the new path is missing: {}'.format(
                            _name, platform.system(),
                            _cur_path.path))
                    self.add_fail(_msg, node=_node)
                else:
                    _msg = (
                        'Reference {} has a path which can be updated for '
                        '{}: {}'.format(
                            _name, platform.system(), _cur_path.path))
                    _fix = wrap_fn(_ref.update, _map_path.path)
                    self.add_fail(_msg, fix=_fix, node=_node)


class CleanBadSceneNodes(core.SCMayaCheck):
    """Clean unwanted scene nodes."""

    _info = 'Checks the scene for unwanted nodes'
    _bad_nodes = {}

    def run(self):
        """Run this check."""
        _types = cmds.allNodeTypes()
        _whitelist = []
        if 'redshift' in dcc.allowed_renderers():
            _whitelist += ['defaultRedshiftPostEffects', 'redshiftOptions']
        for _type in [
                # 'RedshiftOptions',
                # 'RedshiftPostEffects',
                # 'VRaySettingsNode',
                'unknown',
        ]:
            if _type not in _types:
                self.write_log('Type %s does not exist', _type)
                continue
            _nodes = cmds.ls(type=_type) or []
            self.write_log('Found %d %s nodes - %s', len(_nodes), _type, _nodes)
            for _node in _nodes:
                self.write_log('Checking node %s', _node)

                # Ignore whitelisted
                if _node in _whitelist:
                    self.write_log(' - whitelisted')
                    continue

                # Add fail
                if cmds.referenceQuery(_node, isNodeReferenced=True):
                    _ref_node = cmds.referenceQuery(_node, referenceNode=True)
                    _ref = ref.FileRef(_ref_node)
                    _msg = 'Bad {} node {} in ref {}'.format(
                        _type, _node, _ref.namespace)
                    _fail = core.SCFail(_msg, node=_node)
                    _top_node = _ref.find_top_node(catch=True)
                    if _top_node:
                        _action = wrap_fn(cmds.select, _top_node)
                        _fail.add_action('Select ref', _action)
                    self.add_fail(_fail)
                else:
                    _msg = 'Bad {} node {}'.format(_type, _node)
                    _fix = wrap_fn(self._delete_node, _node)
                    self.add_fail(_msg, node=_node, fix=_fix)

    def _delete_node(self, node):
        """Delete the given node.

        Supresses error if the node has already been deleted.

        Args:
            node (str): node to delete
        """
        if cmds.objExists(node):
            cmds.delete(node)


@cache_result
def _find_available_plugins():
    """Search $MAYA_PLUG_IN_PATH for available plugin names.

    Returns:
        (str list): plugin names (eg. stereoCamera, AbcImport)
    """
    _plugins = set()
    for _path in os.environ['MAYA_PLUG_IN_PATH'].split(';'):
        _path = abs_path(_path)
        _dir = Dir(_path)
        if not _dir.exists():
            continue
        _plugins |= {_file.base for _file in _dir.find(
            type_='f', depth=1, extn='mll', full_path=False, class_=True)}
    return sorted(_plugins)


class RemoveBadPlugins(core.SCMayaCheck):
    """Unload unwanted plugins."""

    def run(self):
        """Run this check."""

        _whitelist = []
        if 'redshift' in dcc.allowed_renderers():
            _whitelist.append('redshift4maya')

        # Remove unwanted plugins
        _plugins = cmds.pluginInfo(query=True, listPlugins=True)
        for _plugin in [
                # 'redshift4maya',
                # 'vrayformaya',
                'Mayatomr',
        ]:
            self.write_log('Checking plugin '+_plugin)
            if _plugin in _plugins:
                self.add_fail(
                    'Bad plugin found '+_plugin,
                    fix=wrap_fn(self.fix_bad_plugin, _plugin))

        # Remove unknown plugins
        self.write_log(' - checking unknown plugins')
        _unknown = cmds.unknownPlugin(query=True, list=True) or []
        for _plugin in _unknown:

            if _plugin in _whitelist:
                continue

            if _plugin in _find_available_plugins():
                self.write_log(
                    ' - ignoring available unknown plugin %s', _plugin)
                continue
            if _plugin in ['stereoCamera']:
                self.write_log(
                    ' - ignoring benign unknown plugin %s', _plugin)
                continue

            _msg = 'Scene is requesting missing plugin '+_plugin
            _fix = wrap_fn(cmds.unknownPlugin, _plugin, remove=True)
            self.add_fail(_msg, fix=_fix)

    def fix_bad_plugin(self, plugin, force=False):
        """Unload the given plugin.

        Args:
            plugin (str): name of plugin to unload
            force (bool): force unload plugin without confirmation
        """
        if not force:
            _result = qt.yes_no_cancel(
                'Force unload bad plugin {}?\n\nThis can cause instablity - '
                'you may want to save first.'.format(plugin))
            if _result == 'No':
                return
        cmds.unloadPlugin(plugin, force=True)


class FixRefNodeNames(core.SCMayaCheck):
    """Make sure reference node names match their namespace."""

    def run(self):
        """Run this check."""
        for _ref in self.update_progress(ref.find_refs()):
            self.write_log('Checking ref %s %s', _ref.ref_node, _ref.namespace)
            _good_name = _ref.namespace+'RN'
            if _ref.ref_node == _good_name:
                self.write_log('Checked {} namespace={}'.format(
                    _ref.ref_node, _ref.namespace))
                continue
            _fix = wrap_fn(
                self.fix_ref_node_name, _ref.ref_node, _good_name)
            _msg = 'Reference namespace {} does not match node name {}'.format(
                _ref.namespace, _ref.ref_node)
            self.add_fail(_msg, node=_ref.ref_node, fix=_fix)

    def fix_ref_node_name(self, node, name):
        """Fix reference node name.

        Args:
            node (str): node to fix
            name (str): name to apply
        """
        cmds.lockNode(node, lock=False)
        _node = cmds.rename(node, name)
        cmds.lockNode(_node, lock=True)


class RunMayaScanner(core.SCMayaCheck):
    """Run maya scanner to check for malware."""

    def run(self):
        """Run this check."""
        cmds.loadPlugin('MayaScanner', quiet=True)
        self.write_log('Loaded MayaScanner plugin')
        cmds.MayaScan()
        self.write_log('Ran scan')


class FixViewportCallbacks(core.SCMayaCheck):
    """Fix viewport callbacks CgAbBlastPanelOptChangeCallback error."""

    def run(self):
        """Run this check."""
        self._check_for_cgab_blast_callback()
        self._check_for_dcf_callback()

    def _check_model_editor_callback(self, callback):
        """Search model panels for the given unwanted callback.

        Args:
            callback (str): mel callback to find
        """
        self.write_log('Checking for modeEditor callbacks for %s', callback)
        for _model_panel in cmds.getPanel(typ="modelPanel"):
            _callback = cmds.modelEditor(
                _model_panel, query=True, editorChanged=True)
            if callback in _callback:
                self.write_log(
                    'Found %s in %s callback %s', callback, _model_panel,
                    _callback)
                for _replace in [callback+';', callback]:
                    if _callback.count(_replace) == 1:
                        break
                else:
                    raise NotImplementedError
                _fix = wrap_fn(
                    cmds.modelEditor, _model_panel, edit=True, editorChanged="")
                _msg = 'Found {} callback in modelPanel {}'.format(
                    callback, _model_panel)
                self.add_fail(_msg, fix=_fix)

    def _check_for_cgab_blast_callback(self):
        """Check for CgAbBlastPanelOptChangeCallback callback."""
        self._check_model_editor_callback('CgAbBlastPanelOptChangeCallback')

    def _check_for_dcf_callback(self):
        """Check for DCF_updateViewportList callback."""
        self.write_log('Checking for DCF_updateViewportList')
        _replace = 'DCF_updateViewportList;'
        for _node in cmds.ls(type='script'):
            _before = cmds.scriptNode(_node, query=True, beforeScript=True)
            if not _before or _replace not in _before:
                continue
            _before = _before.replace(_replace, '')
            _msg = ('Found DCF_updateViewportList callback in scriptNode '
                    '{}'.format(_node))
            _fix = wrap_fn(
                cmds.scriptNode, _node, edit=True, beforeScript=_before)
            self.add_fail(_msg, node=_node, fix=_fix)
        self._check_model_editor_callback('DCF_updateViewportList')


class FixDuplicateRenderSetups(core.SCMayaCheck):
    """Fix duplicate render setups.

    This is caused by running duplicate input graph on a node that's
    connected to a render setup.
    """

    def run(self):
        """Run this check."""
        _bad_nodes = set()
        _check_lyrs = [
            _lyr for _lyr in cmds.ls(type='renderLayer')
            if _lyr not in DEFAULT_NODES and
            not cmds.referenceQuery(_lyr, isNodeReferenced=True)]
        for _lyr in self.update_progress(_check_lyrs):

            self.write_log('Found layer %s', _lyr)
            _rs_lyr = single(
                cmds.listConnections(_lyr, type='renderSetupLayer') or [],
                catch=True)
            self.write_log(' - render setup layer %s', _rs_lyr)

            # Check for unconnected legacy layer
            if not _rs_lyr:
                self.add_fail(
                    'Unconnected legacy layer '+_lyr,
                    node=_lyr, fix=wrap_fn(cmds.delete, _lyr))
                _bad_nodes.add(_lyr)
                continue

            # Check for duplicate render setup
            _rs = single(sorted(set(
                cmds.listConnections(_rs_lyr, type='renderSetup'))))
            self.write_log(' - render setup %s', _rs)
            if _rs in DEFAULT_NODES:
                self.write_log(' - node is okay, using active render setup')
                continue
            for _node in [_lyr, _rs_lyr, _rs]:
                if _node in _bad_nodes:
                    continue
                _fix = wrap_fn(cmds.delete, _node)
                self.add_fail(
                    'Unconnected render setup node '+_node,
                    node=_node, fix=_fix)
                _bad_nodes.add(_node)


class CheckReferences(core.SCMayaCheck):
    """Check each reference for common errors."""

    def run(self):
        """Run this check."""
        _cur_ver = dcc.to_version()
        for _ref in pom.find_refs(allow_no_namespace=True):

            self.write_log('Checking ref %s', _ref.namespace)

            # Check for no namespace
            if not _ref.namespace:
                _msg = (
                    'Reference "{}" has no namespace which can make maya '
                    'unstable.'.format(_ref.ref_node))
                _fail = core.SCFail(_msg, node=_ref.ref_node)
                _fail.add_action('Import nodes', _ref.import_, is_fix=True)
                _fail.add_action('Remove', _ref.delete, is_fix=True)
                self.add_fail(_fail)
                return

            _out = pipe.to_output(_ref.path, catch=True)
            if not _out:
                self.write_log(' - off pipeline')
                return
            _top_node = _ref.find_top_node(catch=True)

            # Check size
            _size = _ref.size()
            self.write_log(' - checking size %d %s',
                           _size, nice_size(_size))
            if _size > 500*1000*1000:
                _msg = (
                    'Reference {} is large ({}) - this may cause '
                    'issues'.format(_ref.namespace, nice_size(_size)))
                self.add_fail(_msg, node=_top_node)

            # Check models/rigs have cache sets
            if (
                    _ref_needs_cache_set(_ref) and
                    not cmds.objExists(_ref.to_node('cache_SET', fmt='str'))):
                _msg = (
                    'Reference "{}" is a {} but it has no cache_SET'.format(
                        _ref.namespace, _out.task))
                self.add_fail(_msg, node=_top_node)

            # Check maya ver
            _ref_ver = _out.metadata.get('dcc_version')
            if _ref_ver and _ref_ver > _cur_ver:
                _msg = (
                    'Reference "{}" is from a newer version of maya ({}) which '
                    'can cause issues'.format(
                        _ref.namespace,
                        '.'.join([str(_digit) for _digit in _ref_ver])))
                self.add_fail(_msg, node=_top_node)


def _ref_needs_cache_set(ref_):
    """Test whether the given reference should have a cache set.

    Args:
        ref_ (CMayaRef): reference

    Returns:
        (bool): whether cache set required
    """
    _out = pipe.to_output(ref_.path, catch=True)
    if not _out:
        return False
    if _out.extn in ('abc', ):
        return False
    if _out.asset_type in ('utl', ):
        return False
    if _out.task not in ('model', 'rig'):
        return False
    if _out.entity.name in ('camera', ):
        return False
    return True


class CheckCacheables(core.SCMayaCheck):
    """Check cacheable sets in this scene.

    Used for checking cache refs in referenced assets and CSETS. The
    cache sets should be checked on publish, but they may have accumulated
    duplicate node from contraints for example, which break the abc export
    command.
    """

    def run(self):
        """Run this check."""
        super().run()
        for _cacheable in self.update_progress(m_pipe.find_cacheables()):
            if isinstance(_cacheable, m_pipe.CPCacheableCam):
                self._check_cam(_cacheable)
            elif isinstance(_cacheable, m_pipe.CPCacheableSet):
                self._check_cset(_cacheable)

    def _check_cam(self, cam):
        """Check the given camera.

        Args:
            cam (CPCacheableCam): camera to check
        """
        self._check_shp(cam.cam)

    def _check_cset(self, cset):
        """Check the given CSET.

        Args:
            cset (CPCacheableSet): CSET to check
        """
        _set = cset.node

        _top_nodes = m_pipe.read_cache_set(set_=_set, mode='top')

        # Flag multiple top nodes
        if len(_top_nodes) > 1:
            self.add_fail(
                f'Cache set "{_set}" contains multiple top nodes - this will '
                f'in an abc with multiple top nodes, which is messy in the '
                f'outliner and not nice for people to pick up',
                node=_set)

        # Flag overlapping nodes
        utils.check_set_for_overlapping_nodes(set_=_set, check=self)

        # Check shapes
        self.write_log('Checking shapes %s', cset)
        for _geo in cset.to_geo():
            self.write_log(' - geo %s', _geo)
            self._check_shp(_geo)

        # Check for duplicate names
        _names = collections.defaultdict(list)
        for _node in m_pipe.read_cache_set(
                set_=cset.cache_set, mode='transforms'):
            _names[to_clean(_node)].append(_node)
        for _name, _nodes in _names.items():
            if len(_nodes) == 1:
                continue
            for _node in _nodes[1:]:
                _msg = (
                    f'Duplicate name "{_name}" in "{_set}". This will '
                    'cause errors on abc export.')
                _fix = None
                _fixable = bool([
                    _node for _node in _nodes if not _node.is_referenced()])
                if _fixable:
                    _fix = wrap_fn(
                        self._fix_duplicate_node, node=_node, cbl=cset)
                _fail = core.SCFail(_msg, fix=_fix)
                _fail.add_action('Select nodes', wrap_fn(cmds.select, _nodes))
                self.add_fail(_fail)

    def _fix_duplicate_node(self, node, cbl):
        """Rename a duplicate node so that it has a unique name.

        Args:
            node (str): node to fix
            cbl (CPCacheable): cacheable to fix
        """
        _LOGGER.info('FIX DUP NODE %s', node)

        _tfms = m_pipe.read_cache_set(set_=cbl.cache_set, mode='transforms')
        _names = {to_clean(_tfm) for _tfm in _tfms}
        _LOGGER.info(' - FOUND %d NAMES', len(_names))

        _base = re.split('[|:]', str(node))[-1]
        while _base and _base[-1].isdigit():
            check_heart()
            _base = _base[:-1]
        _LOGGER.info(' - BASE %s', _base)

        # Find next base
        _idx = 1
        _name = _base
        _LOGGER.info(' - CHECK NAME %s', _name)
        while cmds.objExists(_name) or _name in _names:
            check_heart()
            _name = f'{_base}{_idx:d}'
            _LOGGER.info(' - CHECK NAME %s', _name)
            _idx += 1
        _LOGGER.info(' - RENAME %s -> %s', node, _name)
        cmds.rename(node, _name)
