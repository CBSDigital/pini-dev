"""Maya asset checks."""

import os
import collections
import logging

from maya import cmds, mel

from pini import pipe, dcc
from pini.dcc import export_handler
from pini.tools import error
from pini.utils import single, wrap_fn, check_heart, plural

from maya_pini import ref, open_maya as pom, m_pipe, tex
from maya_pini.m_pipe import lookdev
from maya_pini.utils import (
    DEFAULT_NODES, del_namespace, to_clean, add_to_set, to_node, to_long)

from ..core import SCFail, SCMayaCheck, sc_utils_maya

_LOGGER = logging.getLogger(__name__)


class CheckTopNode(SCMayaCheck):
    """Check scene has a single top node matching a given name."""

    task_filter = 'model rig'
    sort = 30

    def run(self):
        """Run this check."""
        _task = pipe.cur_task(fmt='pini')
        _name = {'model': 'MDL', 'rig': 'RIG'}.get(_task)

        _top_nodes = [
            _node for _node in pom.find_nodes(top_node=True, default=False)
            if _node != 'JUNK']
        self.write_log(' - top nodes %s', _top_nodes)

        # Fix no groups at top level
        _top_tfms = [
            _node for _node in _top_nodes
            if isinstance(_node, pom.CTransform)]
        self.write_log(' - top tfms %s', _top_tfms)
        if _top_nodes and not _top_tfms:
            _fix = wrap_fn(
                _create_top_level_group, name=_name, nodes=_top_nodes)
            self.add_fail('No top level {} group'.format(_name), fix=_fix)
            return

        # Fix top nodes not in group
        _top_node = single(_top_nodes, catch=True)
        if _top_nodes and not _top_node:
            _fix = wrap_fn(
                _create_top_level_group, name=_name, nodes=_top_nodes)
            self.add_fail(
                'No single top level {} group'.format(_name), fix=_fix)
            return
        self.write_log('Top node %s', _top_node)
        if _name and _top_node != _name:
            _fix = wrap_fn(cmds.rename, _top_node, _name)
            _msg = 'Badly named top node {} (should be {})'.format(
                _top_node, _name)
            self.add_fail(_msg, fix=_fix, node=_top_node)


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


class CheckCacheSet(SCMayaCheck):
    """Check this scene has a cache set with nodes in it.

    Used for checking assets which will be referenced and cached.
    """

    task_filter = 'model rig layout'
    sort = 40  # Should happen before checks which need cache set
    _ignore_names = None

    def run(self):
        """Run this check."""

        # Check set
        _set = sc_utils_maya.find_cache_set()
        if not _set:
            _fix = wrap_fn(cmds.sets, name='cache_SET', empty=True)
            self.add_fail('Missing cache set', fix=_fix)
            return
        if _set.object_type() != 'objectSet':
            self.add_fail('Bad cache set type')
            return

        # Check set geos
        _geos = sc_utils_maya.read_cache_set_geo()
        self.write_log('Geos %s', _geos)
        if not _geos:
            _fix = None
            _top_node = single(sc_utils_maya.find_top_level_nodes(), catch=True)
            self.write_log('Top node %s', _top_node)
            if _top_node:
                _fix = wrap_fn(add_to_set, _top_node, 'cache_SET')
            _fail = self.add_fail('Empty cache set', fix=_fix)
            return
        self.write_log('GEOS %s', _geos)

        self._check_for_single_top_node()

    def _check_for_single_top_node(self):
        """Make sure cache set geo has a single top node."""
        if not cmds.objExists('cache_SET'):
            return
        _top_nodes = cmds.sets('cache_SET', query=True) or []
        if len(_top_nodes) != 1:
            _msg = ('Cache set should contain one single node to avoid '
                    'abcs with multiple top nodes - cache_SET contains {:d} '
                    'top nodes').format(len(_top_nodes))
            self.add_fail(_msg)


class CheckRenderStats(SCMayaCheck):
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
                _msg = 'Bad render setting: "{}" set to "{}"'.format(
                    _plug, {True: 'on', False: 'off'}[_plug.get_val()])
                _fix = wrap_fn(_plug.set_val, _val)
                self.add_fail(_msg, fix=_fix, node=geo)


class CheckForEmptyNamespaces(SCMayaCheck):
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
            self.add_fail('Empty namespace {}'.format(_ns), fix=_fix)


class CheckUVs(SCMayaCheck):
    """Check UVs on current scene geo."""

    task_filter = 'model rig'
    _label = 'Check UVs'
    depends_on = (CheckCacheSet, )

    def run(self):
        """Run this check."""
        _geos = sc_utils_maya.read_cache_set_geo()
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
        self.write_log('Checking geo %s cur=%s, sets=%s', geo, _set, _sets)

        # Flag no uv sets
        if not _set:
            _msg = 'Geo {} has no uvs'.format(geo)
            self.add_fail(_msg, node=geo)
            return

        # Flag current set is not map1
        if _set != 'map1':
            if 'map1' in _sets:
                _msg = 'Geo {} is not using uv set map1 (set is {})'.format(
                    geo, _set)
                _fix = wrap_fn(sc_utils_maya.fix_uvs, geo)
                self.add_fail(_msg, node=geo, fix=_fix)
            else:
                _msg = ('Geo {} does not have uv set map1 (set is '
                        '{})'.format(geo, _set))
                _fix = wrap_fn(sc_utils_maya.fix_uvs, geo)
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
                    'Geo {} is using empty uv set map1 (should use '
                    '{})'.format(geo, _set))
                _fix = wrap_fn(sc_utils_maya.fix_uvs, geo)
                self.add_fail(_msg, node=geo, fix=_fix)
            else:
                _msg = 'Geo {} is using has empty uv set map1'.format(geo)
                self.add_fail(_msg, node=geo)
            return

        # Flag unused sets
        if len(_sets) > 1:
            _unused = sorted(set(_sets) - set(['map1']))
            _msg = 'Geo {} has unused uv set{}: {}'.format(
                geo, plural(_sets[1:]), ', '.join(_unused))
            _fix = wrap_fn(sc_utils_maya.fix_uvs, geo)
            self.add_fail(_msg, node=geo, fix=_fix)


class CheckModelGeo(SCMayaCheck):
    """Check naming of cache set geometry."""

    task_filter = 'model'
    _ignore_names = None
    depends_on = (CheckCacheSet, )

    def run(self):
        """Run this check."""

        _geos = m_pipe.read_cache_set()
        for _geo in _geos:
            for _plug in _geo.tfm_plugs:
                if _plug.find_incoming():
                    self.add_fail(
                        'Plug has incoming connections: "{}"'.format(_plug),
                        fix=_plug.break_connections)


class CheckGeoNaming(SCMayaCheck):
    """Check naming of cache set geometry."""

    task_filter = 'model rig layout'
    _ignore_names = None
    depends_on = (CheckCacheSet, )

    # Should happen late as renames geo
    sort = 90

    def run(self):
        """Run this check."""
        _geos = sc_utils_maya.read_cache_set_geo()
        self.write_log('GEOS %s', _geos)
        if self._check_for_duplicates(geos=_geos):
            return
        self._check_geos(geos=_geos)

    def _check_geos(self, geos):
        """Check geometry in cache set.

        Args:
            geos (str list): cache set geometry

        Returns:
            (dict): dictionary of node names and nodes using that
                name (eg. {'GEO': ['test:GEO', 'GEO']}) - this is
                used to flag duplicates
        """
        _names = collections.defaultdict(list)
        self._ignore_names = []
        for _geo in geos:
            self._check_geo(_geo)

    def _check_geo(self, geo):
        """Apply check to the given geo.

        Args:
            geo (str): transform of mesh to check
        """
        self.write_log(' - checking geo %s', geo)

        # Check shapes
        _geo_ss = cmds.listRelatives(
            geo, shapes=True, noIntermediate=True, path=True) or []
        if len(_geo_ss) > 1:
            _msg = 'Geo {} has muliple shapes {}'.format(
                geo, _geo_ss)
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
                _msg, _fix, _suggestion = sc_utils_maya.fix_node_suffix(
                    node=_grp, suffix='_GRP',
                    alts=['_Grp', '_gr'], type_='group',
                    ignore=self._ignore_names)
                self._ignore_names.append(_suggestion)
                self.add_fail(_msg, node=geo, fix=_fix)
            return
        _geo_s = single(_geo_ss)
        self.write_log('   - shape %s', _geo_s)

        # Check for namespace
        _refs_mode = export_handler.get_publish_references_mode()
        _import = export_handler.ReferencesMode.IMPORT_INTO_ROOT_NAMESPACE
        if geo.namespace and _refs_mode != _import:
            _clean_name = to_clean(geo)
            _fix = wrap_fn(cmds.rename, geo, _clean_name)
            _msg = 'Geo "{}" is using a namespace'.format(geo)
            self.add_fail(_msg, fix=_fix, node=geo)
            return

        # Check geo name
        _name = to_clean(geo)
        _geo_suffix = os.environ.get('PINI_SANITY_CHECK_GEO_SUFFIX', 'GEO')
        if not (_name.endswith('_'+_geo_suffix) or _name == _geo_suffix):
            _msg, _fix, _suggestion = sc_utils_maya.fix_node_suffix(
                node=geo, suffix='_'+_geo_suffix,
                alts=['_Geo', '_GEO', '_geo', '_geom'], type_='geo',
                ignore=self._ignore_names)
            self._ignore_names.append(_suggestion)
            self.add_fail(_msg, node=geo, fix=_fix)
            return

        # Check shape name
        _cur_name = to_clean(geo.shp)
        _good_name = to_clean(geo)+'Shape'
        self.write_log(
            '   - good name %s instanced=%d', _good_name,
            geo.shp.is_instanced())
        if not geo.shp.is_instanced() and _cur_name != _good_name:
            _msg = ('Geo {} does not have matching shape name {} (shape '
                    'is currently {})'.format(geo, _good_name, _geo_s))
            _fix = wrap_fn(self.fix_bad_shape, _geo_s, _good_name)
            self.add_fail(_msg, fix=_fix, node=geo)
            return

    def _check_for_duplicates(self, geos):
        """Flag for duplicate nodes in the cache set.

        Args:
            geos (str list): geometry
        """
        _names = collections.defaultdict(list)
        for _geo in geos:
            _name = to_clean(_geo)
            _names[_name].append(_geo)

        _dup_names = False
        for _name, _geos in _names.items():
            if len(_geos) == 1:
                continue
            self.write_log('Duplicate names %s', _geos)
            _fail = SCFail('Duplicate name {} in cache_SET: {}'.format(
                _name, _geos))
            _sel = wrap_fn(cmds.select, _geos)
            _fail.add_action('Select nodes', _sel)
            _fix = wrap_fn(self.fix_duplicate_nodes, _geos)
            _fail.add_action('Fix', _fix)
            self.add_fail(_fail)
            _dup_names = True

        return _dup_names

    def fix_bad_shape(self, shp, name):
        """Fix bad shape name.

        Args:
            shp (str): shape to fix
            name (str): new name to apply
        """
        _LOGGER.debug('FIX BAD SHAPE %s -> %s', shp, name)

        # Check for name clash
        if cmds.objExists(name):
            _node = pom.cast_node(name, maintain_shapes=True)
            assert _node.plug['intermediateObject'].get_val()
            _node.rename(name+'Undeformed')

        cmds.rename(shp, name)

    def fix_duplicate_nodes(self, nodes):
        """Fix duplicate nodes.

        Args:
            nodes (str): duplicate nodes to fix
        """
        _name = str(nodes[0]).split('|')[-1]
        _root = _name
        while _root[0].isdigit():
            _root = _root[:-1]
        for _node in nodes[1:]:
            _idx = 1
            _new_name = None
            while True:
                check_heart()
                _new_name = '{}{:d}'.format(_root, _idx)
                _idx += 1
                if cmds.objExists(_new_name):
                    continue
                break
            if not cmds.objExists(_node):
                _LOGGER.warning(' - MISSING NODE %s', _node)
                continue
            cmds.rename(_node, _new_name)


class CheckForNgons(SCMayaCheck):
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
                _msg = 'Mesh "{}" contains ngons'.format(_geo)
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


class FindUnneccessarySkinClusters(SCMayaCheck):
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

        _geos = sc_utils_maya.read_cache_set_geo()
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
                '{} has a skinCluster with no blendShape and a single '
                'input joint - this can cause bloat in abcs and cause '
                'memory issues'.format(_geo.shp))
            self.add_fail(_msg, node=_geo.shp)


class CheckForFaceAssignments(SCMayaCheck):
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
                _msg = 'Shader "{}" has face assigment{}: {}'.format(
                    _shd, plural(_assigns),
                    ', '.join([
                        '"{}"'.format(_assign) for _assign in _assigns]))
                _fix = wrap_fn(
                    self._fix_face_assignment, geo=_geo, shader=_shd)
                _fail = SCFail(_msg, node=_geo)
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
        except ValueError:
            raise error.HandledError(
                'Failed to unassign "{}" from "{}".'
                '\n\n'
                'It seems like maya is having trouble with this assignment.'
                'Try deleting history on this node or removing it '
                'if possible'.format(shader, geo))
        shader.assign_to(geo)


class CheckShaders(SCMayaCheck):
    """Check the shader name matches the shading engine.

    eg. myShader -> myShaderSE
    """

    sort = 100
    task_filter = 'lookdev'
    depends_on = (CheckForFaceAssignments, )

    def run(self, check_ai_shd=True):
        """Run this check.

        Args:
            check_ai_shd (bool): check any attached arnold shader override
        """

        # Check for referenced shaders
        for _shd in lookdev.read_shader_assignments(fmt='shd', referenced=True):
            _fix = wrap_fn(sc_utils_maya.import_referenced_shader, _shd)
            self.add_fail(
                'Shader "{}" is referenced - this must be imported into the '
                'current scene'.format(str(_shd)),
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
                _msg = 'Shader {} is using a namespace'.format(_shd)
                _fix = wrap_fn(cmds.rename, _shd, to_clean(_shd))
                self.add_fail(_msg, fix=_fix, node=_shd)
                continue

            # Flag missing MTL suffix
            if not _shd.endswith('_MTL'):
                _msg, _fix, _suggestion = sc_utils_maya.fix_node_suffix(
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
                if sc_utils_maya.shd_is_arnold(engine=_se, type_=_type):
                    _msg = 'Shader {} ({}) is not arnold shader'.format(
                        _shd, _type)
                    self.add_fail(_msg, node=_shd)
                    continue

                # Check ai shader suffix
                _ai_shd = _data.get('ai_shd')
                _base = _shd[:-4]
                if check_ai_shd and _ai_shd:
                    if not _ai_shd.endswith('_AIS'):
                        _msg, _fix, _suggestion = sc_utils_maya.fix_node_suffix(
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
                _fail = SCFail(
                    'Shader "{}" is face assignment "{}".'.format(
                        shader, _assign),
                    node=_assign)
                _fail.add_action('Select shader', wrap_fn(cmds.select, shader))
                self.add_fail(_fail)
                return

            # Catch duplicate node
            if '|' in _assign:
                _fail = SCFail(
                    'Shader "{}" is assigned to duplicate node "{}".'.format(
                        shader, _assign),
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
                'Shader "{}" is assigned to intermediate object "{}" '
                'which is not renderable. This assigment has no effect '
                'and may bloat the publish file.'.format(
                    shader, _geo))
            _fix = wrap_fn(
                self._unassign_shader, engine=engine, geo=_geo)
            _fail = SCFail(_msg, node=_geo)
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
        _good_name = shd[:-4]+'_SG'
        if _good_name == engine:
            self.write_log(' - shading engine %s is good', engine)
            return

        _msg = ('Shading engine {} name does not match shader {} (should '
                'be {})'.format(engine, shd, _good_name))
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
            _fail = SCFail(
                'Shader "{}" is not assigned to referenced geometry, which '
                'can lead to a mismatch between the geometry names in the '
                'model/rig and the assignment - this could cause shaders to '
                'fail to attach.'.format(shd))
            _fail.add_action('Select shader', wrap_fn(cmds.select, shd))
            _fail.add_action('Select nodes', wrap_fn(cmds.select, _assigns))
            self.add_fail(_fail)


class NoObjectsWithDefaultShader(SCMayaCheck):
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
                    _msg = 'Geo "{}" has default shader "{}" applied'.format(
                        _geo, _shd)
                    self.add_fail(_msg, node=_geo)
                    _flagged_geos.add(_geo)

            # Check for default shading group
            if _se in DEFAULT_NODES:
                for _geo in _geos:
                    if _geo in _flagged_geos:
                        continue
                    _msg = (
                        'Geo "{}" has shader "{}" applied which uses default '
                        'shading engine "{}" - this will cause issues as '
                        'default nodes do not appear in references'.format(
                            _geo, _shd, _se))
                    self.add_fail(_msg, node=_geo)
