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
    abs_path, Dir, is_camel, to_camel)

from maya_pini import ref, open_maya as pom, m_pipe
from maya_pini.utils import DEFAULT_NODES, to_clean

from ..core import SCFail, SCMayaCheck

_LOGGER = logging.getLogger(__name__)


class CheckUnmappedPaths(SCMayaCheck):
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


class CleanBadSceneNodes(SCMayaCheck):
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
                    _fail = SCFail(_msg, node=_node)
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


class RemoveBadPlugins(SCMayaCheck):
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


class FixRefNodeNames(SCMayaCheck):
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


class RunMayaScanner(SCMayaCheck):
    """Run maya scanner to check for malware."""

    def run(self):
        """Run this check."""
        cmds.loadPlugin('MayaScanner', quiet=True)
        self.write_log('Loaded MayaScanner plugin')
        cmds.MayaScan()
        self.write_log('Ran scan')


class FixViewportCallbacks(SCMayaCheck):
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


class FixDuplicateRenderSetups(SCMayaCheck):
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


class CheckLookdevAssign(SCMayaCheck):
    """Check lookdev assignments have been applied correctly.

    If a node is missing from the target reference or if the target node
    doesn't have the correct lookdev shader applied then this is flagged.
    """

    def run(self):
        """Run this check."""
        for _lookdev in dcc.find_pipe_refs(task='lookdev'):
            if not _lookdev.ref:
                continue
            self.write_log('Checking %s', _lookdev)
            _lookdev_ref = _lookdev.ref
            _geo_ns = _lookdev_ref.namespace[:-4]
            _geo_ref = ref.find_ref(_geo_ns)
            if not _geo_ref:
                self.write_log(' - No geo ref found %s', _geo_ns)
                continue
            _shd_data = _lookdev.shd_data.get('shds', {})
            for _, _data in _shd_data.items():
                _geos = _data['geos']
                _sg = _data['shadingEngine']
                self._check_shd_assignments(
                    lookdev_ref=_lookdev_ref, geo_ref=_geo_ref, geos=_geos,
                    sg=_sg)

    def _check_shd_assignments(self, lookdev_ref, geo_ref, sg, geos):
        """Check assignments for the given lookdev.

        Args:
            lookdev_ref (CMayaLookdevRef): lookdev ref
            geo_ref (CMayaReference): geometery ref
            sg (str): shading group to check
            geos (str list): geos using this shader
        """

        # Read shading group
        if sg == 'initialShadingGroup':
            return

        # Check shading group
        _node_fail = _check_lookdev_node(ref_=lookdev_ref, node=sg)
        if _node_fail:
            self.add_fail(_node_fail)
            return
        _sg = pom.CNode(lookdev_ref.to_node(sg))
        self.write_log(' - Check shading group %s', _sg)

        # Get list of assigned shapes
        _sg_geos = set()
        _sg_items = pom.CMDS.sets(_sg, query=True) or []
        for _sg_shp in _sg_items:
            _sg_geo = _sg_shp.to_parent()
            _sg_geos.add(_sg_geo)
        _sg_geos = sorted(_sg_geos)

        # Check geos have shader assigned
        for _geo in geos:

            # Check node exists
            _geo = geo_ref.to_node(_geo)
            try:
                _geo = pom.CNode(_geo)
            except RuntimeError:
                _msg = 'Failed to apply lookdev {} to missing node {}'.format(
                    lookdev_ref.namespace, _geo)
                _node = geo_ref.find_top_node(catch=True)
                self.add_fail(_msg, node=_node)
                continue

            # Check assignment
            if _geo not in _sg_geos:
                _geo_s = _geo.to_shp(catch=True)
                if not _geo_s:
                    _msg = (
                        'Geo "{}" is missing a shape node - failed to apply '
                        'to lookdev "{}" (shading group "{}")'.format(
                            _geo, lookdev_ref.namespace, _sg))
                    self.add_fail(_msg, node=_geo)
                else:
                    _msg = (
                        'Lookdev "{}" not applied to "{}" (shading group '
                        '"{}")'.format(
                            lookdev_ref.namespace, _geo, _sg))
                    _fix = wrap_fn(cmds.sets, _geo_s, forceElement=_sg)
                    self.add_fail(_msg, node=_geo, fix=_fix)


def _check_lookdev_node(ref_, node):
    """Check a lookdev reference has a node referred to in its yaml.

    Args:
        ref_ (FileRef): lookdev ref
        node (str): required node

    Returns:
        (SCFail|None): missing node fail (if any)
    """
    _node = ref_.to_node(node)
    if cmds.objExists(_node):
        return None
    _msg = (
        'Node {} is missing from the lookdev reference {} which means '
        'that there is something wrong with the publish'.format(
            _node, ref_.namespace))
    _fail = SCFail(_msg, node=ref_.ref_node)
    return _fail


class CheckAOVs(SCMayaCheck):
    """Check current scene AOVs match the job template.

    If no job AOV template has been published, the check does nothing.
    """

    task_filter = 'lookdev layout lighting'
    label = 'Check AOVs'

    def run(self):
        """Run this check."""
        _aovs = [_aov for _aov in pom.CMDS.ls(type='aiAOV')
                 if not _aov.is_referenced()]
        self._check_for_broken_cryto_aovs(_aovs)
        self._check_for_job_default_aovs(_aovs)

    def _check_for_broken_cryto_aovs(self, aovs):
        """Check for broken cryto AOVs.

        Args:
            aovs (CNode list): AOVs to check
        """
        self.write_log('Check for broken cryto AOVs')

        # Find crypto aovs to check
        _aovs = [_aov for _aov in aovs
                 if _aov.plug['name'].get_val().startswith('crypto_')]
        self.write_log(' - AOVs %s', _aovs)
        if not _aovs:
            self.write_log(' - Nothing to check')
            return

        # Find shader
        _shds = pom.find_nodes(type_='cryptomatte')
        self.write_log(
            ' - cryptomatte shaders: %s', [str(_shd) for _shd in _shds])
        if len(_shds) > 1:
            _msg = 'Too many crypto shaders (see log for details)'
            self.add_fail(_msg)
            return
        if not _shds:
            _msg = 'Missing cryptomatte shader'
            _fix = wrap_fn(pom.CMDS.shadingNode, 'cryptomatte', asShader=True)
            self.add_fail(_msg, fix=_fix)
            return
        _shd = single(_shds)
        _shd_col = _shd.plug['outColor']
        self.write_log(' - cryptomatte shader: %s %s', _shd, _shd_col)

        # Check connections
        for _aov in _aovs:
            self.write_log(' - checking aov: %s', _aov)
            _shd_plug = _aov.plug['defaultValue']
            if not _shd_plug.find_incoming():
                _msg = 'AOV "{}" not connected to shader "{}"'.format(
                    _aov.plug['name'].get_val(), _shd)
                _fix = wrap_fn(_shd_col.connect, _shd_plug)
                self.add_fail(_msg, fix=_fix, node=_aov)

    def _check_for_job_default_aovs(self, aovs):
        """Check scene AOVs match job defaults (if available).

        Args:
            aovs (CNode list): AOVs to check
        """
        self.write_log('Check for job default AOVs')

        _job = pipe.cur_job()
        if not _job:
            self.write_log(' - No current job')
            return
        _yml = pipe.cur_job().to_file('.pini/aovs.yml')
        if not _yml.exists():
            self.write_log(' - No AOVs set up for this job %s', _yml.path)
            return

        # Check AOVs match job AOVs
        self.write_log('Read yml %s', _yml.path)
        _yml_aovs = _yml.read_yml()
        for _aov in aovs:
            _name = _aov.plug['name'].get_val()
            if _name in _yml_aovs:
                del _yml_aovs[_name]
                self.write_log(' - matched aov %s', _name)

        for _aov, _data in _yml_aovs.items():
            _msg = (
                'Job AOV "{}" is missing from the scene'.format(_aov))
            _fix = wrap_fn(_create_aov, _aov, type_=_data.get('type'))
            self.add_fail(_msg, fix=_fix)


def _create_aov(name, type_):
    """Create the given AOV.

    Args:
        name (str): AOV name
        type_ (str): AOV type
    """
    from mtoa import aovs

    cmds.lockNode('initialParticleSE', lock=False, lockUnpublished=False)

    _LOGGER.info('ADD AOV %s type=%s', name, type_)
    _api = aovs.AOVInterface()
    _match = (
        "setAttr: The attribute 'initialParticleSE.aiCustomAOVs[0]"
        ".aovName' is locked or connected and cannot be modified.")
    try:
        _api.addAOV(name, aovType=type_)
    except RuntimeError as _exc:
        _exc = str(_exc).strip()
        if _exc != _match:
            _LOGGER.info(' - ERROR "%s"', _exc)
            _LOGGER.info(' - MATCH "%s"', _match)
            raise _exc


class CheckCustomAovConnections(SCMayaCheck):
    """Check custom aov assignments.

    Checks the names of the custom aov connections to each shading group
    matches the name of the aov in the lookdev scene.
    """

    label = 'Check custom AOV connections'

    def run(self):
        """Run this check."""
        for _lookdev in dcc.find_pipe_refs(task='lookdev'):
            if not _lookdev.ref:
                continue
            self.write_log('Checking %s', _lookdev)
            _ref = _lookdev.ref
            _custom_aovs = _lookdev.shd_data.get('custom_aovs', [])
            for _src, _aov in _custom_aovs:

                # Check node
                _node_fail = _check_lookdev_node(ref_=_ref, node=_src)
                if _node_fail:
                    self.add_fail(_node_fail)
                    continue

                _src = pom.CPlug(_ref.to_plug(_src))
                self._check_custom_aov(src=_src, aov=_aov)

    def _check_custom_aov(self, src, aov):
        """Check the given custom aov setting from the lookdev scene.

        Args:
            src (str): plug being applied to custom aov list
            aov (str): name of aov which it was applied to
        """
        _LOGGER.debug('CHECK CUSTOM AOV %s %s', src, aov)
        self.write_log('   - aov %s %s', src, aov)

        # Read current custom aov connection
        _cur_trg = single(
            src.find_outgoing(type_='shadingEngine'), catch=True)
        if not _cur_trg:
            return

        # Read name of current aov
        _LOGGER.debug(' - CUR TRG %s %s', _cur_trg, type(_cur_trg))
        _tokens = re.split(r'[\[\]]', str(_cur_trg))
        _LOGGER.debug(' - TOKENS %s', _tokens)
        _, _idx, _ = _tokens
        _idx = int(_idx)
        _sg = pom.to_node(_cur_trg)
        _name_attr = _sg.to_attr(
            'aiCustomAOVs[{:d}].aovName'.format(_idx))
        _cur_aov = cmds.getAttr(_name_attr)
        if _cur_aov == aov:
            self.write_log(' - connected correctly')
            return

        # Find correct connection index
        _idxs = []
        for _idx in cmds.getAttr(
                _sg.to_plug('aiCustomAOVs'), multiIndices=True):
            _name_attr = _sg.to_attr(
                'aiCustomAOVs[{:d}].aovName'.format(_idx))
            _name = cmds.getAttr(_name_attr)
            if _name == aov:
                _idxs.append(_idx)
        _idx = single(_idxs, catch=True)
        if not _idx:
            _msg = (
                'Custom aov {aov} is wrongly connected to {cur_aov} in '
                '{sg} - no {aov} aov was found to connect to'.format(
                    aov=aov, cur_aov=_cur_aov, sg=_sg))
            self.add_fail(_msg, node=_sg)
            return

        # Build fix with new target
        _new_trg = _sg.to_attr('aiCustomAOVs[{:d}].aovInput'.format(_idx))
        _cur_conn = src, _cur_trg
        _new_conn = src, _new_trg
        _msg = ('Custom aov {} is wrongly connected to {} in {}'.format(
            aov, _cur_aov, _sg))
        _fix = wrap_fn(
            _fix_bad_aov_conn, disconnect=_cur_conn, connect=_new_conn)
        self.add_fail(_msg, node=_sg, fix=_fix)


def _fix_bad_aov_conn(disconnect, connect):
    """Fix bad a bad aov connection.

    Args:
        disconnect (tuple): connection to break
        connect (tuple): connection to build
    """
    cmds.disconnectAttr(*disconnect)
    cmds.connectAttr(*connect)


class CheckReferences(SCMayaCheck):
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
                _fail = SCFail(_msg, node=_ref.ref_node)
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
                    not cmds.objExists(_ref.to_node('cache_SET'))):
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
        ref_ (CMayaReference): reference

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


class CheckCacheables(SCMayaCheck):
    """Check cacheable sets in this scene.

    Used for checking cache refs in referenced assets and CSETS. The
    cache sets should be checked on publish, but they may have accumulated
    duplicate node from contraints for example, which break the abc export
    command.
    """

    def run(self):
        """Run this check."""
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

        # Check shapes
        for _geo in cset.to_geo():
            self._check_shp(_geo)

        # Check for duplicate nodes
        _names = collections.defaultdict(list)
        for _node in cset.to_geo():
            _names[to_clean(_node)].append(_node)
        for _name, _nodes in _names.items():
            if len(_nodes) == 1:
                continue
            for _node in _nodes[1:]:
                _msg = 'Duplicate node {} in {}'.format(
                    _node, cset.cache_set)
                _fix = wrap_fn(self._fix_duplicate_node, _node)
                self.add_fail(_msg, node=_node, fix=_fix)

    def _fix_duplicate_node(self, node):
        """Rename a duplicate node so that it has a unique name.

        Args:
            node (str): node to fix
        """
        _base = re.split('[|:]', node)[-1]
        while _base and _base[-1].isdigit():
            check_heart()
            _base = _base[:-1]
        _idx = 1
        _name = _base
        while cmds.objExists(_name):
            check_heart()
            _name = '{}{:d}'.format(_base, _idx)
            _idx += 1
        cmds.rename(node, _name)


class CheckRenderGlobals(SCMayaCheck):
    """Check render format is exr."""

    task_filter = 'lighting model lookdev'

    def run(self):
        """Run this check."""

        _ren = cmds.getAttr('defaultRenderGlobals.currentRenderer')

        if _ren == 'arnold' and 'arnold' in dcc.allowed_renderers():

            if not cmds.objExists('defaultArnoldDriver'):
                _msg = (
                    'Missing defaultArnoldDriver - try opening render globals')
                self.add_fail(_msg)
                return

            # Check image format
            _plug = pom.CPlug('defaultArnoldDriver.aiTranslator')
            _cur_fmt = _plug.get_val()
            _task = pipe.cur_task(fmt='pini')
            _req_fmt = {'lighting': 'exr',
                        'model': 'png',
                        'lookdev': 'png'}[_task]
            if _cur_fmt != _req_fmt:
                _fix = wrap_fn(_plug.set_val, _req_fmt)
                _msg = 'Image format is not {} (set to {})'.format(
                    _req_fmt, _cur_fmt)
                self.add_fail(_msg, fix=_fix, node=_plug.node)

            # Check arnold settings
            for _attr, _val in [
                    ('mergeAOVs', True),
                    ('exrTiled', False),
                    ('halfPrecision', True)
            ]:
                _plug = pom.CNode('defaultArnoldDriver').plug[_attr]
                if _plug.get_val() == _val:
                    continue
                _msg = '{} is not set to {}'.format(_plug, _val)
                _fix = wrap_fn(_plug.set_val, _val)
                self.add_fail(_msg, fix=_fix, node=_plug.node)


class CheckRenderLayers(SCMayaCheck):
    """Check current scene render layers."""

    task_filter = 'lighting model lookdev'

    def run(self):
        """Run this check."""

        _prefixes = ['bty', 'mte', 'sdw', 'ref', 'utl']
        for _lyr in pom.find_render_layers():
            self.write_log('Checking %s pass=%s', _lyr, _lyr.pass_name)

            if _lyr.pass_name == 'masterLayer':
                continue

            if '_' in _lyr.pass_name:
                _prefix, _suffix = _lyr.pass_name.split('_', 1)
            else:
                _prefix, _suffix = _lyr.pass_name, None

            # Check prefix
            if _prefix not in _prefixes:
                _msg = (
                    'Render layer "{}" has prefix "{}" which is not in the '
                    'list of approved prefixes: {}'.format(
                        _lyr.pass_name, _prefix, str(_prefixes).strip('[]')))
                self.add_fail(_msg, node=_lyr)
                continue

            # Check suffix
            if _suffix and not is_camel(_suffix):
                _new_suffix = to_camel(_suffix)
                _new_name = '{}_{}'.format(_prefix, _new_suffix)
                _msg = (
                    'Render layer "{}" has suffix "{}" which is not camel '
                    'case (should be "{}")'.format(
                        _lyr.pass_name, _suffix, _new_name))
                _fix = wrap_fn(_lyr.set_pass_name, _new_name)
                self.add_fail(_msg, node=_lyr, fix=_fix)
                continue
