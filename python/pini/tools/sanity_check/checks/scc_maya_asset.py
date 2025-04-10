"""Maya asset checks."""

import os
import logging

from maya import cmds, mel

from pini import pipe, dcc
from pini.dcc import export
from pini.tools import error
from pini.utils import single, wrap_fn, plural

from maya_pini import ref, open_maya as pom, m_pipe, tex
from maya_pini.m_pipe import lookdev
from maya_pini.utils import (
    DEFAULT_NODES, del_namespace, to_clean, add_to_set, to_node, to_long)

from .. import core, utils

_LOGGER = logging.getLogger(__name__)


class CheckAssetHierarchy(core.SCMayaCheck):
    """Check scene has a single top node matching a given name."""

    action_filter = 'Publish'
    task_filter = 'model rig'
    sort = 30

    def run(self, req_nodes=None):
        """Run this check.

        Args:
            req_nodes (dict): dict of required nodes in hierarchy
        """

        # Determine required node hierarchy
        _task = pipe.cur_task(fmt='pini')
        _req_nodes = req_nodes or self.settings.get('nodes', {}).get(_task, {})
        if not _req_nodes:
            _req_nodes = {
                'model': {'MDL': None},
                'rig': {'RIG': None}}.get(_task, {})
        self.write_log('req nodes %s', _req_nodes)
        if not _req_nodes:
            return
        _req_top_node = single(
            _node for _node in _req_nodes.keys() if _node != 'JUNK')
        self.write_log('req top node %s', _req_top_node)

        # Fix no groups at top level
        _top_nodes = pom.find_nodes(top_node=True, default=False)
        _top_tfms = [_node for _node in _top_nodes if not _node.shp]
        self.write_log(' - top tfms %s', _top_tfms)
        if _top_nodes and not _top_tfms:
            _fix = wrap_fn(
                _create_top_level_group, name=_req_top_node,
                nodes=_top_nodes)
            self.add_fail(
                f'No top level "{_req_top_node}" group', fix=_fix)
            return

        # Fix badly named top node
        _top_node = pom.find_node(
            top_node=True, default=False, filter_='-JUNK', catch=True)
        if _top_node and _top_node != _req_top_node:
            _fix = wrap_fn(cmds.rename, _top_node, _req_top_node)
            _msg = (
                f'Badly named top node "{_top_node}" (should be '
                f'"{_req_top_node}")')
            self.add_fail(_msg, fix=_fix, node=_top_node)
            return

        # Check hierarchy
        if not self._check_hierarchy(_req_nodes):
            return
        _top_node = _req_top_node

        # Fix top nodes not in group
        _extra_top_nodes = [
            _node for _node in pom.find_nodes(top_node=True, default=False)
            if _node not in (_top_node, 'JUNK')]
        self.write_log(' - extra top nodes %s', _top_nodes)
        if _extra_top_nodes:
            for _node in _extra_top_nodes:
                self.add_fail(
                    f'Top node "{_node}" outside "{_top_node}"',
                    fix=wrap_fn(cmds.parent, _node, _top_node))
            return

    def _check_hierarchy(self, nodes, parent=None):
        """Check the given node hierarchy exists.

        Args:
            nodes (dict): node hierarchy to check
            parent (str): path to parent node (eg. |RIG|ABC)

        Returns:
            (bool): whether check passed
        """
        _passed = True
        _parent = parent or ''
        for _node, _children in nodes.items():

            _node = f'{_parent}|{_node}'
            self.write_log('check %s', _node)
            if not cmds.objExists(_node):
                _parent, _name = _node.rsplit('|', 1)
                _kwargs = {}
                if _parent:
                    _kwargs['parent'] = _parent
                self.write_log('check %s', _node)
                self.add_fail(
                    f'Missing node "{_node}"',
                    fix=wrap_fn(
                        cmds.group, name=_name, empty=True, **_kwargs))
                _passed = False

            if _children:
                if not self._check_hierarchy(nodes=_children, parent=_node):
                    _passed = False

        return _passed


def _create_top_level_group(name, nodes):
    """Create top level group containing the given nodes.

    Args:
        name (str): group name
        nodes (CBaseTransform list): nodes to add to group
    """
    for _node in nodes:
        if _node == name:
            continue
        _node.add_to_grp(name)


class CheckCacheSet(core.SCMayaCheck):
    """Check this scene has a cache set with nodes in it.

    Used for checking assets which will be referenced and cached.
    """

    task_filter = 'model rig layout'
    sort = 40  # Should happen before checks which need cache set
    _ignore_names = None

    def run(self, top_node_priority=None):
        """Run this check.

        Args:
            top_node_priority (str list): override top node priority
                sorting (eg. ['ABC', 'RIG'])
        """
        super().run()

        _task = pipe.cur_task()
        _top_node_priority = top_node_priority
        if not _top_node_priority:
            _top_node_priority = self.settings.get(
                'top_node_priority', {}).get(_task)
        _top_node_priority = _top_node_priority or []
        self.write_log('top node priority %s', _top_node_priority)

        # Check set
        _set = utils.find_cache_set()
        if not _set:
            _fix = wrap_fn(cmds.sets, name='cache_SET', empty=True)
            self.add_fail('Missing cache set', fix=_fix)
            return
        if _set.object_type() != 'objectSet':
            self.add_fail('Bad cache set type')
            return

        # Check set geos
        _geos = m_pipe.read_cache_set(set_=_set, mode='geo')
        _tfms = m_pipe.read_cache_set(set_=_set, mode='tfm')
        self.write_log('Geos %s', _geos)
        if not _geos:

            # Find top node
            _top_node = None
            for _node in _top_node_priority:
                if cmds.objExists(_node):
                    _top_node = _node
                    break
            else:
                _top_node = single(utils.find_top_level_nodes(), catch=True)
            self.write_log('Top node %s', _top_node)

            _fix = None
            if _top_node:
                _fix = wrap_fn(add_to_set, _top_node, 'cache_SET')
            if _tfms:
                _msg = 'No geo in cache set'
            else:
                _msg = 'Empty cache set'
            self.add_fail(_msg, fix=_fix)
            return

        # Check for referenced geo in cache set
        _ref_mode = export.get_pub_refs_mode()
        _import_refs = export.PubRefsMode.IMPORT_TO_ROOT
        _refd_geo = [_geo for _geo in _geos if _geo.is_referenced()]
        self.write_log('Referenced geos %s', _refd_geo)
        if _refd_geo and _ref_mode != _import_refs:
            _fix = wrap_fn(export.set_pub_refs_mode, _import_refs)
            self.add_fail(
                f'Referenced geo in cache set but references mode is '
                f'set to "{_ref_mode.value}" (should be '
                f'"{_import_refs.value}")',
                fix=_fix)
            return

        utils.check_cacheable_set(set_=_set, check=self)


class CheckRenderStats(core.SCMayaCheck):
    """Check render stats section on shape nodes."""

    task_filter = 'model rig layout'
    sort = 40  # Should happen before checks which need cache set
    _ignore_names = None
    depends_on = (CheckCacheSet, )

    def run(self):
        """Run this check."""

        _geos = m_pipe.read_cache_set()
        if not _geos:
            self.add_fail('No geo in cache_SET')
        for _geo in _geos:
            self._check_geo(_geo)

    def _check_geo(self, geo):
        """Apply check to the given geo.

        Args:
            geo (str): transform of mesh to check
        """
        self.write_log(' - checking geo %s', geo)

        # Check render stats
        for _attr, _val in [
                ('castsShadows', True),
                ('receiveShadows', True),
                ('holdOut', False),
                ('motionBlur', True),
                ('primaryVisibility', True),
                ('smoothShading', True),
                ('visibleInReflections', True),
                ('visibleInRefractions', True),
                ('doubleSided', True),
        ]:
            _plug = geo.shp.plug[_attr]
            if _plug.get_val() != _val:
                _val = {True: 'on', False: 'off'}[_plug.get_val()]
                _msg = f'Bad render setting: "{_plug}" set to "{_val}"'
                _fix = wrap_fn(_plug.set_val, _val)
                self.add_fail(_msg, fix=_fix, node=geo)


class CheckForEmptyNamespaces(core.SCMayaCheck):
    """Check scene for empty namespaces."""

    profile_filter = 'asset'

    def run(self):
        """Run this check."""
        _refs = ref.find_refs()
        _ref_nss = [_ref.namespace for _ref in _refs]
        _all_nss = cmds.namespaceInfo(
            listOnlyNamespaces=True, recurse=True) or []
        _nss = sorted({
            str(_ns.split(':')[0])
            for _ns in _all_nss})
        self.write_log('Found %s namespaces %s', len(_nss), _nss)
        for _ns in _nss:
            if _ns in _ref_nss:
                self.write_log('Allowed ref namespace %s', _ns)
                continue
            if _ns in ['shared', 'UI']:
                self.write_log('Allowed standard namespace %s', _ns)
                continue
            _nodes = cmds.namespaceInfo(_ns, listNamespace=True)
            if _nodes:
                self.write_log('Allowed namespace with nodes %s', _ns)
                continue
            _fix = wrap_fn(del_namespace, _ns)
            self.write_log('Found empty namespace %s', _ns)
            self.add_fail(f'Empty namespace {_ns}', fix=_fix)


class CheckUVs(core.SCMayaCheck):
    """Check UVs on current scene geo."""

    task_filter = 'model rig'
    _label = 'Check UVs'
    depends_on = (CheckCacheSet, )

    def run(self):
        """Run this check."""
        _geos = utils.read_cache_set_geo()
        if not _geos:
            self.add_fail('No geo found')
        for _geo in _geos:
            self._check_geo(_geo)

    def _check_geo(self, geo):
        """Check uvs on the given piece of geometry.

        Args:
            geo (str): geometry to check
        """

        # Ignore no shapes
        if not cmds.listRelatives(geo, shapes=True, noIntermediate=True):
            return

        # Read current/all uv sets
        _set = single(
            cmds.polyUVSet(geo, query=True, currentUVSet=True) or [],
            catch=True)
        _sets = cmds.polyUVSet(geo, query=True, allUVSets=True) or []
        _fix = wrap_fn(utils.fix_uvs, geo)
        self.write_log('Checking geo %s cur=%s, sets=%s', geo, _set, _sets)

        # Flag no uv sets
        if not _set:
            _msg = f'Geo "{geo}" has no uvs'
            self.add_fail(_msg, node=geo)
            return

        # Flag current set is not map1
        if _set != 'map1':
            if 'map1' in _sets:
                _msg = (
                    f'Geo "{geo}" is not using uv set "map1" '
                    f'(set is "{_set}")')
                self.add_fail(_msg, node=geo, fix=_fix)
            else:
                _msg = (
                    f'Geo {geo} does not have uv set "map1" '
                    f'(set is "{_set}")')
                self.add_fail(_msg, node=geo, fix=_fix)
            return

        # Flag map1 has no area
        if not cmds.polyEvaluate(geo, uvArea=True, uvSetName=_set):
            _set = single([
                _set for _set in _sets
                if cmds.polyEvaluate(geo, uvArea=True, uvSetName=_set)],
                catch=True)
            if _set:
                _msg = (
                    f'Geo "{geo}" is using empty uv set "map1" (should use '
                    f'"{_set}")')
                self.add_fail(_msg, node=geo, fix=_fix)
            else:
                _msg = f'Geo "{geo}" empty uv set "map1"'
                self.add_fail(_msg, node=geo, fix=_fix)
            return

        # Flag unused sets
        if len(_sets) > 1:
            _unused = sorted(set(_sets) - set(['map1']))
            _unused_s = ', '.join(f'"{_set}"' for _set in _unused)
            _msg = (
                f'Geo "{geo}" has unused uv set{plural(_sets[1:])}: '
                f'{_unused_s}')
            self.add_fail(_msg, node=geo, fix=_fix)


class CheckModelGeo(core.SCMayaCheck):
    """Check naming of cache set geometry."""

    task_filter = 'model'
    _ignore_names = None
    depends_on = (CheckCacheSet, )

    def run(self):
        """Run this check."""

        _geos = m_pipe.read_cache_set()
        self.write_log('Found %d geos: %s', len(_geos), _geos)
        for _geo in _geos:
            for _plug in _geo.tfm_plugs:
                if _plug.find_incoming():
                    self.add_fail(
                        f'Plug has incoming connections: "{_plug}"',
                        fix=_plug.break_conns)


class CheckGeoNaming(core.SCMayaCheck):
    """Check naming of cache set geometry."""

    task_filter = 'model rig layout'
    _ignore_names = None
    depends_on = (CheckCacheSet, )

    # Should happen late as renames geo
    sort = 90

    def run(self):
        """Run this check."""
        _geos = utils.read_cache_set_geo()
        self.write_log('geos %s', _geos)
        self._ignore_names = []
        for _geo in _geos:
            self._check_geo(_geo)

    def _check_geo(self, geo):
        """Apply check to the given geo.

        Args:
            geo (str): transform of mesh to check
        """
        self.write_log(' - checking geo %s ref=%d', geo, geo.is_referenced())

        # Check shapes
        _geo_ss = cmds.listRelatives(
            geo, shapes=True, noIntermediate=True, path=True) or []
        if len(_geo_ss) > 1:
            _msg = f'Geo "{geo}" has muliple shapes: {_geo_ss}'
            self.add_fail(_msg, node=geo)
            return
        _geo_s = single(_geo_ss, catch=True)
        if not _geo_s:
            _grp = geo
            _type = cmds.objectType(_grp)
            if _type.endswith('Constraint'):
                return
            if (
                    not _grp.endswith('_GRP') and
                    to_clean(_grp) not in ['GEO', 'RIG', 'MDL', 'LYT']):
                _msg, _fix, _suggestion = utils.fix_node_suffix(
                    node=_grp, suffix='_GRP',
                    alts=['_Grp', '_gr'], type_='group',
                    ignore=self._ignore_names)
                self._ignore_names.append(_suggestion)
                self.add_fail(_msg, node=geo, fix=_fix)
            return
        _geo_s = single(_geo_ss)
        self.write_log('   - shape %s', _geo_s)

        # Check for namespace
        _refs_mode = export.get_pub_refs_mode()
        _import = export.PubRefsMode.IMPORT_TO_ROOT
        if geo.namespace and _refs_mode != _import:
            _clean_name = to_clean(geo)
            if geo.is_referenced():
                _fix = None
            else:
                _fix = wrap_fn(cmds.rename, geo, _clean_name)
            _msg = f'Geo "{geo}" is using a namespace'
            self.add_fail(_msg, fix=_fix, node=geo)
            return

        # Check geo name
        _name = to_clean(geo)
        _geo_suffix = os.environ.get('PINI_SANITY_CHECK_GEO_SUFFIX', 'GEO')
        if not (_name.endswith('_' + _geo_suffix) or _name == _geo_suffix):
            _msg, _fix, _suggestion = utils.fix_node_suffix(
                node=geo, suffix='_' + _geo_suffix,
                alts=['_Geo', '_GEO', '_geo', '_geom'], type_='geo',
                ignore=self._ignore_names)
            self._ignore_names.append(_suggestion)
            self.add_fail(_msg, node=geo, fix=_fix)
            return


class CheckForCameras(core.SCMayaCheck):
    """Check for cameras in rigs/models."""

    task_filter = 'model rig'

    def run(self):
        """Run this check."""
        for _cam in pom.find_nodes('camera'):
            _long = to_long(_cam)
            self.write_log('Check cam %s %s', _cam, _long)
            if _long.startswith('|JUNK'):
                continue
            if _cam in DEFAULT_NODES:
                continue
            self.add_fail(f'Camera {_cam}', node=_cam)


class CheckForNgons(core.SCMayaCheck):
    """Check for polygons with more than four sides."""

    task_filter = 'model'
    depends_on = (CheckGeoNaming, )
    sort = 100

    def run(self):
        """Run this check."""
        for _geo in self.update_progress(m_pipe.read_cache_set()):
            cmds.select(_geo)
            mel.eval(
                'polyCleanupArgList 4 { '
                '    "0","2","1","0","1","0","0","0","0","1e-05","0",'
                '    "1e-05","0","1e-05","0","-1","0","0" }')
            if cmds.ls(selection=True):
                _msg = f'Mesh "{_geo}" contains ngons'
                self.add_fail(
                    _msg, node=_geo, fix=wrap_fn(self.fix_ngons, _geo))

    def fix_ngons(self, geo):
        """Fix ngons in the given mesh.

        Args:
            geo (str): mesh to fix
        """
        cmds.select(geo)
        mel.eval(
            'polyCleanupArgList 4 {'
            '    "0","1","1","0","1","0","0","0","0","1e-05","0",'
            '    "1e-05","0","1e-05","0","-1","0","0" }')
        cmds.select(geo)


class FindUnneccessarySkinClusters(core.SCMayaCheck):
    """Find skin clusters which are not needed.

    If a skin cluster is used where a constraint can be used, this can
    cause bloat on AbcExport. The exporter sees the skin cluster and
    determines that it needs to export the geo as a point cloud rather
    than just exporting transform information. This means that every
    point position is exported on every frame, which can cause memory
    issues and unnecessarily large abcs.
    """

    task_filter = 'model rig'
    depends_on = (CheckCacheSet, )

    def run(self):
        """Run this check."""

        _geos = utils.read_cache_set_geo()
        if not _geos:
            self.add_fail('No geo found')

        for _geo in self.update_progress(_geos):

            self.write_log('Checking %s', _geo)

            # Ignore nodes with blendShape
            _hist = cmds.listHistory(
                _geo.shp, pruneDagObjects=True, interestLevel=2) or []
            _blend = [_node for _node in _hist
                      if cmds.objectType(_node) == 'blendShape']
            if _blend:
                continue

            # If skin cluster, check has more than one joint input
            _skin = single(
                cmds.listConnections(
                    _geo.shp, type='skinCluster', destination=False) or [],
                catch=True)
            if not _skin:
                continue
            _jnts = sorted(set(cmds.listConnections(
                _skin, type='joint', destination=False)))
            if len(_jnts) != 1:
                continue

            _msg = (
                f'Shape "{_geo.shp}" has a skinCluster with no blendShape '
                f'and a single input joint - this can cause bloat in abcs '
                f'and cause memory issues')
            self.add_fail(_msg, node=_geo.shp)


class CheckForFaceAssignments(core.SCMayaCheck):
    """Checks for shaders assigned to faces rather than geometry."""

    task_filter = 'lookdev'

    def run(self):
        """Run this check."""
        _LOGGER.debug('CHECK FOR FACE ASSIGNMENTS')
        for _se in self.update_progress(cmds.ls(type='shadingEngine')):

            # Deterine shader
            self.write_log('Checking %s ', _se)
            _shd = tex.to_shd(_se)
            if not _shd:
                continue
            self.write_log(' - shader %s ', _shd)

            # Find relevant face assignments
            _face_assigns = {}
            for _assign in _shd.to_geo(faces=True):
                self.write_log(' - checking face assignment %s', _assign)
                _long = to_long(_assign)
                if _long.startswith('|JUNK'):
                    continue
                _geo = to_node(_assign)
                _face_assigns[_geo] = _shd

            # Add fails
            for _geo, _shd in _face_assigns.items():
                _assigns = _shd.to_geo(node=_geo, faces=True)
                _assigns_s = ', '.join(f'"{_assign}"' for _assign in _assigns)
                _msg = (
                    f'Shader "{_shd}" has face assigment{plural(_assigns)}: '
                    f'{_assigns_s}')
                _fix = wrap_fn(
                    self._fix_face_assignment, geo=_geo, shader=_shd)
                _fail = core.SCFail(_msg, node=_geo)
                _fail.add_action(
                    'Select shader', wrap_fn(cmds.select, _shd))
                _fail.add_action('Fix', _fix, is_fix=True)
                self.add_fail(_fail)

    def _fix_face_assignment(self, shader, geo):
        """Fix shader face assignment.

        Args:
            shader (Shader): shader with face assignment
            geo (str): geometry to apply
        """
        _LOGGER.info('FIX FACE ASSIGNMENTS %s %s', shader, geo)
        try:
            shader.unassign(node=geo)
        except ValueError as _exc:
            raise error.HandledError(
                f'Failed to unassign "{shader}" from "{geo}".'
                '\n\n'
                'It seems like maya is having trouble with this assignment.'
                'Try deleting history on this node or removing it '
                'if possible') from _exc
        shader.assign_to(geo)


class CheckShaders(core.SCMayaCheck):
    """Check the shader name matches the shading engine.

    eg. myShader -> myShaderSE
    """

    sort = 100
    action_filter = 'LookdevPublish'
    task_filter = 'lookdev'
    depends_on = (CheckForFaceAssignments, )

    def run(self, check_ai_shd=True):
        """Run this check.

        Args:
            check_ai_shd (bool): check any attached arnold shader override
        """

        # Check for referenced shaders
        for _shd in lookdev.read_shader_assignments(fmt='shd', referenced=True):
            _fix = wrap_fn(utils.import_referenced_shader, _shd)
            self.add_fail(
                f'Shader "{_shd}" is referenced - this must be imported into '
                'the current scene',
                node=_shd, fix=_fix)

        _shds = lookdev.read_shader_assignments(
            catch=True, allow_face_assign=True, referenced=False)
        self.write_log('Found %d shaders: %s', len(_shds), _shds)
        if not _shds:
            self.add_fail(
                'No shader assignments found - this publish saves out shading '
                'assignments so you need to apply shaders to your geometry')
        _ren = cmds.getAttr('defaultRenderGlobals.currentRenderer')
        _ignore_names = set()
        for _shd, _data in _shds.items():

            self.write_log('Checking shader %s', _shd)

            if _shd == 'lambert1':
                continue

            _se = _data['shadingEngine']
            self.write_log(' - shading engine %s', _se)
            _type = cmds.objectType(_shd)
            _select_shd = wrap_fn(cmds.select, _shd)

            # Flag namespace
            if _shd != to_clean(_shd):
                _msg = f'Shader "{_shd}" is using a namespace'
                _fix = wrap_fn(cmds.rename, _shd, to_clean(_shd))
                self.add_fail(_msg, fix=_fix, node=_shd)
                continue

            # Flag missing MTL suffix
            if not _shd.endswith('_MTL'):
                _msg, _fix, _suggestion = utils.fix_node_suffix(
                    _shd, suffix='_MTL', alts=['_shd', '_mtl', '_SHD', '_Mat'],
                    type_='shader', ignore=_ignore_names)
                _ignore_names.add(_suggestion)
                self.add_fail(_msg, fix=_fix, node=_shd)
                continue

            self._check_engine_name(shd=_shd, engine=_se)
            self._flag_assigned_to_intermediate_node(engine=_se, shader=_shd)
            self._check_for_unreferenced_geo(_shd)

            if _ren == 'arnold' and 'arnold' in dcc.allowed_renderers():

                # Flag non-arnold shader
                if utils.shd_is_arnold(engine=_se, type_=_type):
                    _msg = f'Shader "{_shd}" ({_type}) is not arnold shader'
                    self.add_fail(_msg, node=_shd)
                    continue

                # Check ai shader suffix
                _ai_shd = _data.get('ai_shd')
                _base = _shd[:-4]
                if check_ai_shd and _ai_shd:
                    if not _ai_shd.endswith('_AIS'):
                        _msg, _fix, _suggestion = utils.fix_node_suffix(
                            _ai_shd, suffix='_AIS',
                            alts=['_shd', '_mtl', '_SHD'],
                            type_='ai shader', base=_base, ignore=_ignore_names)
                        _ignore_names.add(_suggestion)
                        self.add_fail(_msg, fix=_fix, node=_ai_shd)

    def _flag_assigned_to_intermediate_node(self, engine, shader):
        """Flag geo assigned to intermediate nodes.

        Args:
            engine (str): shading engine
            shader (str): shader
        """
        _shd = tex.to_shd(shader)
        _assigns = _shd.to_assignments()
        self.write_log(' - assigns %s', _assigns)

        for _assign in _assigns:

            # Check for face assigns
            if '.f[' in _assign:
                _fail = core.SCFail(
                    f'Shader "{shader}" is face assignment "{_assign}".',
                    node=_assign)
                _fail.add_action('Select shader', wrap_fn(cmds.select, shader))
                self.add_fail(_fail)
                return

            # Catch duplicate node
            if '|' in _assign:
                _fail = core.SCFail(
                    f'Shader "{shader}" is assigned to duplicate node '
                    f'"{_assign}".',
                    node=_assign)
                _fail.add_action('Select shader', wrap_fn(cmds.select, shader))
                self.add_fail(_fail)
                return

            _geo = pom.cast_node(_assign, maintain_shapes=True)
            self.write_log(' - check geo %s %s', _geo, _geo.object_type())
            if _geo.object_type() != 'mesh':
                continue
            self.write_log('   - is mesh')
            if not _geo.plug['intermediateObject'].get_val():
                continue
            _msg = (
                f'Shader "{shader}" is assigned to intermediate object '
                f'"{_geo}" which is not renderable. This assigment has '
                f'no effect and may bloat the publish file.')
            _fix = wrap_fn(
                self._unassign_shader, engine=engine, geo=_geo)
            _fail = core.SCFail(_msg, node=_geo)
            _fail.add_action('Select shader', wrap_fn(cmds.select, shader))
            _fail.add_action('Fix', _fix, is_fix=True)
            self.add_fail(_fail)

    def _unassign_shader(self, engine, geo):
        """Unassign a shader from the given geometry.

        Args:
            engine (str): shading engine (set)
            geo (str): geometry to detatch
        """
        cmds.sets(geo, edit=True, remove=engine)

    def _check_engine_name(self, shd, engine):
        """Check shading group matches shader.

        Args:
            shd (str): shader to check
            engine (str): shading engine
        """
        if shd == 'lambert1':
            return
        if cmds.referenceQuery(shd, isNodeReferenced=True):
            return

        self.write_log('Checking shd %s', shd)
        assert shd.endswith('_MTL')
        _good_name = shd[:-4] + '_SG'
        if _good_name == engine:
            self.write_log(' - shading engine %s is good', engine)
            return

        _msg = (
            f'Shading engine "{engine}" name does not match shader "{shd}" '
            f'(should be "{_good_name}")')
        _fix = wrap_fn(cmds.rename, engine, _good_name)
        self.add_fail(_msg, fix=_fix, node=shd)

    def _check_for_unreferenced_geo(self, shd):
        """Check for shaders which are not applied to referenced geometry.

        Args:
            shd (str): shader node
        """
        _shd = tex.to_shd(shd)
        _ref = None
        _assigns = _shd.to_assignments()
        for _assign in _assigns:
            try:
                _node = pom.cast_node(_assign)
            except ValueError:
                continue
            if not _node.is_referenced():
                continue
            _ref = pom.find_ref(_node.namespace)
            break
        if not _ref:
            _fail = core.SCFail(
                f'Shader "{shd}" is not assigned to referenced geometry, '
                'which can lead to a mismatch between the geometry names in '
                'the model/rig and the assignment - this could cause '
                'shaders to fail to attach.')
            _fail.add_action('Select shader', wrap_fn(cmds.select, shd))
            _fail.add_action('Select nodes', wrap_fn(cmds.select, _assigns))
            self.add_fail(_fail)


class NoObjectsWithDefaultShader(core.SCMayaCheck):
    """Lookdev check to make sure no geos have default shader assigned."""

    task_filter = 'lookdev'
    depends_on = (CheckForFaceAssignments, )

    def run(self):
        """Run this check."""
        _shds = lookdev.read_shader_assignments()

        _flagged_geos = set()
        for _shd, _data in _shds.items():

            _se = _data['shadingEngine']
            _geos = _data['geos']

            # Check for default shader
            if _shd in DEFAULT_NODES:
                for _geo in _geos:
                    _msg = f'Geo "{_geo}" has default shader "{_shd}" applied'
                    self.add_fail(_msg, node=_geo)
                    _flagged_geos.add(_geo)

            # Check for default shading group
            if _se in DEFAULT_NODES:
                for _geo in _geos:
                    if _geo in _flagged_geos:
                        continue
                    _msg = (
                        f'Geo "{_geo}" has shader "{_shd}" applied which uses '
                        f'default shading engine "{_se}" - this will cause '
                        f'issues as default nodes do not appear in references')
                    self.add_fail(_msg, node=_geo)
