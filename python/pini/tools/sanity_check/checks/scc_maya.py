"""Maya specific sanity checks."""

import collections
import logging
import os
import platform

from maya import cmds

from pini import qt, dcc, pipe
from pini.utils import (
    single, wrap_fn, nice_size, cache_result, Path, abs_path, Dir)

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
                        f'Reference {_name} has a path which can be updated '
                        f'for {platform.system()} but the new path is missing: '
                        f'{_cur_path.path}')
                    self.add_fail(_msg, node=_node)
                else:
                    _msg = (
                        f'Reference {_name} has a path which can be updated '
                        f'for {platform.system()}: {_cur_path.path}')
                    _fix = wrap_fn(_ref.update, _map_path.path)
                    self.add_fail(_msg, fix=_fix, node=_node)


class CleanBadSceneNodes(core.SCMayaCheck):
    """Clean unwanted scene nodes."""

    _info = 'Checks the scene for unwanted nodes'
    _bad_nodes = {}

    def run(self):
        """Run this check."""
        _whitelist = []
        if 'redshift' in dcc.allowed_renderers():
            _whitelist += ['defaultRedshiftPostEffects', 'redshiftOptions']

        # Get list of nodes
        _nodes = []
        _all_types = cmds.allNodeTypes()
        for _type in [
                # 'RedshiftOptions',
                # 'RedshiftPostEffects',
                # 'VRaySettingsNode',
                'unknown',
        ]:
            if _type not in _all_types:
                self.write_log('Type %s does not exist', _type)
                continue
            _type_nodes = cmds.ls(type=_type) or []
            self.write_log(
                'Found %d %s nodes - %s', len(_type_nodes), _type, _type_nodes)
            for _node in _type_nodes:
                _nodes.append((_node, _type))

        # Check nodes
        for _node, _type in self.update_progress(_nodes):
            self.write_log('Checking node %s (%s)', _node, _type)

            # Ignore whitelisted
            if _node in _whitelist:
                self.write_log(' - whitelisted')
                continue

            # Add fail
            if cmds.referenceQuery(_node, isNodeReferenced=True):
                continue
            _msg = f'Bad {_type} node {_node}'
            _fix = wrap_fn(utils.safe_delete, _node)
            self.add_fail(_msg, node=_node, fix=_fix)


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


class CheckPlugins(core.SCMayaCheck):
    """Check plugins status."""

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
            self.write_log('Checking plugin ' + _plugin)
            if _plugin in _plugins:
                self.add_fail(
                    'Bad plugin found ' + _plugin,
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
            _msg = 'Scene is requesting missing plugin ' + _plugin
            _fix = wrap_fn(cmds.unknownPlugin, _plugin, remove=True)
            self.add_fail(_msg, fix=_fix)

        # Disable slow autoload
        for _plugin in [
                'MASH', 'bifrostGraph', 'bifrostshellnode', 'bifrostvisplugin']:
            self.write_log('Checking autoload ' + _plugin)
            if _plugin not in _plugins:
                self.write_log(' - not available')
                continue
            if cmds.pluginInfo(_plugin, query=True, autoload=True):
                self.add_fail(
                    f'Plugin "{_plugin}" is set to autoload - this can slow '
                    f'down maya launch time', fix=wrap_fn(
                        cmds.pluginInfo, _plugin, edit=True, autoload=False))

    def fix_bad_plugin(self, plugin, force=False):
        """Unload the given plugin.

        Args:
            plugin (str): name of plugin to unload
            force (bool): force unload plugin without confirmation
        """
        if not force:
            _result = qt.yes_no_cancel(
                f'Force unload bad plugin {plugin}?\n\nThis can cause '
                f'instablity - you may want to save first.')
            if _result == 'No':
                return
        cmds.unloadPlugin(plugin, force=True)


class FixRefNodeNames(core.SCMayaCheck):
    """Make sure reference node names match their namespace."""

    def run(self):
        """Run this check."""
        for _ref in self.update_progress(ref.find_refs()):
            self.write_log('Checking ref %s %s', _ref.ref_node, _ref.namespace)
            _good_name = _ref.namespace + 'RN'
            if _ref.ref_node == _good_name:
                self.write_log(
                    'Checked %s namespace=%s', _ref.ref_node, _ref.namespace)
                continue
            _fix = wrap_fn(
                self.fix_ref_node_name, _ref.ref_node, _good_name)
            _msg = (
                f'Reference namespace {_ref.namespace} does not match node '
                f'name {_ref.ref_node}')
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
                for _replace in [callback + ';', callback]:
                    if _callback.count(_replace) == 1:
                        break
                else:
                    raise NotImplementedError
                _fix = wrap_fn(
                    cmds.modelEditor, _model_panel, edit=True, editorChanged="")
                _msg = f'Found {callback} callback in modelPanel {_model_panel}'
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
            _msg = (
                f'Found DCF_updateViewportList callback in scriptNode '
                f'"{_node}"')
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
                    'Unconnected legacy layer ' + _lyr,
                    node=_lyr, fix=wrap_fn(utils.safe_delete, _lyr))
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
                _fix = wrap_fn(utils.safe_delete, _node)
                self.add_fail(
                    'Unconnected render setup node ' + _node,
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
            if not _ref.namespace and not _ref.prefix:
                _msg = (
                    f'Reference "{_ref.ref_node}" has no namespace or prefix '
                    f'which can make maya unstable.')
                _fail = core.SCFail(_msg, node=_ref.ref_node)
                _fail.add_action('Import nodes', _ref.import_, is_fix=True)
                _fail.add_action('Remove', _ref.delete, is_fix=True)
                self.add_fail(_fail)
                continue

            _out = pipe.to_output(_ref.path, catch=True)
            if not _out:
                self.write_log(' - off pipeline')
                continue
            _top_node = _ref.find_top_node(catch=True)

            # Check size
            _size = _ref.size()
            self.write_log(' - checking size %d %s',
                           _size, nice_size(_size))
            if _size > 500 * 1000 * 1000:
                _size_s = nice_size(_size)
                _msg = (
                    f'Reference {_ref.namespace} is large ({_size_s}) - '
                    f'this may cause issues')
                self.add_fail(_msg, node=_top_node)

            # Check models/rigs have cache sets
            if (
                    _ref_needs_cache_set(_ref) and
                    not cmds.objExists(_ref.to_node('cache_SET', fmt='str'))):
                _msg = (
                    f'Reference "{_ref.namespace}" is a {_out.task} but it '
                    f'has no cache_SET')
                self.add_fail(_msg, node=_top_node)

            # Check maya ver
            _ref_ver = _out.metadata.get('dcc_version')
            if _ref_ver and _ref_ver > _cur_ver:
                _ver = '.'.join([str(_digit) for _digit in _ref_ver])
                _msg = (
                    f'Reference "{_ref.namespace}" is from a newer version '
                    f'of maya ({_ver}) which can cause issues')
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
        for _cbl in self.update_progress(m_pipe.find_cacheables()):
            self.write_log('check cacheable %s', _cbl)
            if isinstance(_cbl, m_pipe.CPCacheableCam):
                self._check_cam(_cbl)
            elif isinstance(_cbl, m_pipe.CPCacheableSet):
                self._check_cset(_cbl)
            elif isinstance(_cbl, m_pipe.CPCacheableRef):
                self._check_ref_for_dup_nodes(_cbl)

    def _check_cam(self, cam):
        """Check the given camera.

        Args:
            cam (CPCacheableCam): camera to check
        """
        self.check_shp(cam.cam)

    def _check_cset(self, cset):
        """Check the given CSET.

        Args:
            cset (CPCacheableSet): CSET to check
        """
        utils.check_cacheable_set(set_=cset.node, check=self)

    def _check_ref_for_dup_nodes(self, ref_):
        """Check a referenced cache set for duplicate node.

        This can occur if a reference is accidentally duplicated, causing
        all the cache_SET geo to be duplicated and breaking AbcExport.

        Args:
            ref_ (CPCacheableRef): cache ref to check
        """

        # Find name clashes
        _cache_set = ref_.to_node('cache_SET')
        _nodes = ref_.to_nodes(mode='all')
        self.write_log(' - found %d nodes', len(_nodes))
        _map = collections.defaultdict(list)
        for _node in _nodes:
            _map[to_clean(_node)].append(_node)
        _unrefd_nodes = [
            _node for _node in _nodes if not _node.is_referenced()]
        _clashes = []
        for _clean, _o_nodes in _map.items():
            if len(_o_nodes) <= 1:
                continue
            _clashes.append(_o_nodes)
        self.write_log(' - found %d clashes', len(_clashes))
        self.write_log(' - found %d unreferenced', len(_unrefd_nodes))

        # Handle clashes - batch handle large numbers of fails
        if len(_clashes) > 20:
            if _unrefd_nodes:
                self.add_fail(
                    f'Cachable "{_cache_set}" has name clashes and there are '
                    f'{len(_unrefd_nodes)} unreferenced nodes in it',
                    node=_cache_set,
                    fix=wrap_fn(utils.safe_delete, _unrefd_nodes))
            else:
                self.add_fail(
                    f'Cachable "{_cache_set}" has name clashes',
                    node=_cache_set)
        elif _clashes:
            for _nodes in _clashes:
                _refd = [_node for _node in _nodes if _node.is_referenced()]
                _unrefd_nodes = [
                    _node for _node in _nodes if _node not in _refd]
                if len(_refd) == 1:
                    _node = single(_refd)
                    _unrefd_s = ', '.join(
                        [str(_node) for _node in _unrefd_nodes])
                    self.add_fail(
                        f'Geo "{_node}" in "{_cache_set}" has unreferenced '
                        f'name clash: {_unrefd_s}',
                        node=_cache_set,
                        fix=wrap_fn(utils.safe_delete, _unrefd_nodes))
                else:
                    self.add_fail(
                        f'Set "{_cache_set}" has name clash: {_nodes}')
