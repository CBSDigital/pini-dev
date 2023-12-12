"""Maya asset checks."""

import collections
import logging

from maya import cmds

from pini import qt, pipe
from pini.tools import sanity_check
from pini.utils import single, wrap_fn, check_heart, plural

from maya_pini import ref, open_maya as pom
from maya_pini.m_pipe import lookdev
from maya_pini.utils import (
    DEFAULT_NODES, del_namespace, to_clean, to_unique, to_shp)

from ..core import SCFail, SCMayaCheck

_LOGGER = logging.getLogger(__name__)


def _cache_set_to_geos(set_=None, shapes=False):
    """Get a list of geometry in the current scene's cache_SET.

    By default this is a list of all transforms.

    Args:
        set_ (str): cache set to read (if not default)
        shapes (bool): return shapes rather than transforms

    Returns:
        (str list): geos
    """
    _geos = []
    _set = set_ or 'cache_SET'
    if not cmds.objExists(_set):
        return []
    for _root in cmds.sets(_set, query=True) or []:
        _children = cmds.listRelatives(
            _root, allDescendents=True, type='transform', path=True) or []
        for _geo in [_root]+_children:
            if not shapes:
                _geos.append(_geo)
            else:
                _geo_ss = cmds.listRelatives(
                    _geo, shapes=True, noIntermediate=True, path=True) or []
                _geos += _geo_ss
    return _geos


def _fix_node_suffix(node, suffix, type_, alts=(), ignore=(), base=None):
    """Provide fix for node suffix fail.

    Args:
        node (str): node with bad suffix
        suffix (str): required suffix (eg. _GEO)
        type_ (str): node type (for fail message - eg. geo)
        alts (tuple): possible altertives values to strip (eg. _Geo, _geo)
        ignore (tuple): suggestions to ignore
        base (str): apply name base/prefix

    Returns:
        (str, fn, str): fail message, fix, name suggestion
    """
    _LOGGER.debug("FIX NODE SUFFIX %s", node)

    if cmds.referenceQuery(node, isNodeReferenced=True):
        _msg = ('Referenced {} {} does not have "{}" '
                'suffix'.format(type_, node, suffix))
        return _msg, None, None

    # Determine base
    _base = base
    if not _base:
        _splitters = [suffix] + list(alts)
        _LOGGER.debug(' - SPLITTERS %s', _splitters)
        for _splitter in _splitters:
            if _splitter in node:
                _base = node.rsplit(_splitter, 1)[0]
                break
        else:
            _base = node
        while _base[-1].isdigit():
            _base = _base[:-1]
    _LOGGER.debug(' - BASE %s', _base)

    # Build suggestion
    _suggestion = to_unique(base=_base, suffix=suffix, ignore=ignore)
    _LOGGER.debug(' - SUGGESTION %s', _suggestion)
    _msg = (
        '{} "{}" does not have "{}" suffix (suggestion: '
        '"{}")'.format(type_.capitalize(), node, suffix, _suggestion))
    _fix = wrap_fn(cmds.rename, node, _suggestion)

    return _msg, _fix, _suggestion


def _is_display_points(node):
    """Test whether the given node is a display points node.

    These nodes are listed as dag nodes but do not appear in outliner
    or have parents.

    Args:
        node (str): node to test

    Returns:
        (bool): whether display points
    """
    _node = pom.CTransform(node)
    if not _node.shp:
        return False
    return _node.shp.object_type() == 'displayPoints'


class CheckTopNode(SCMayaCheck):
    """Check scene has a single top node matching a given name."""

    task_filter = 'model rig'

    def run(self):
        """Run this check."""
        _task = pipe.cur_task(fmt='pini')
        _name = {'model': 'MDL', 'rig': 'RIG'}[_task]

        # Read top nodes
        _top_nodes = [
            str(_node.strip('|')) for _node in cmds.ls(dag=True, long=True)
            if _node.count('|') == 1 and
            not _node.strip('|') in DEFAULT_NODES and
            not cmds.referenceQuery(_node, isNodeReferenced=True) and
            not _is_display_points(_node)]
        if 'JUNK' in _top_nodes:
            _top_nodes.remove('JUNK')
        self.write_log('TOP NODES %s', _top_nodes)

        _top_node = single(_top_nodes, catch=True)
        if not _top_node:
            self.add_fail('No single top node')
            return
        self.write_log('Top node %s', _top_node)
        if _top_node != _name:
            _fix = wrap_fn(cmds.rename, _top_node, _name)
            _msg = 'Badly named top node {} (should be {})'.format(
                _top_node, _name)
            self.add_fail(_msg, fix=_fix, node=_top_node)


class CheckCacheSet(SCMayaCheck):
    """Check this scene has a cache set with nodes in it.

    Used for checking assets which will be referenced and cached.
    """

    task_filter = 'model rig layout'
    sort = 40  # Should happen before checks which need cache set
    _ignore_names = None

    def run(self):
        """Run this check."""
        self._check_set()
        self._check_for_single_top_node()

    def _check_set(self):
        """Check cache_SET exists and has geometry.

        Returns:
            (str list): cache set geometry
        """
        if not cmds.objExists('cache_SET'):
            _fix = wrap_fn(cmds.sets, name='cache_SET', empty=True)
            self.add_fail('Missing cache set', fix=_fix)
            return []
        if not cmds.objectType('cache_SET') == 'objectSet':
            self.add_fail('Bad cache set type')
            return []

        _geos = _cache_set_to_geos()
        if not _geos:
            self.add_fail('Empty cache set')

        self.write_log('GEOS %s', _geos)
        return _geos

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

    def run(self):
        """Run this check."""

        _geos = _cache_set_to_geos()
        if not _geos:
            self.add_fail('Empty cache set')
        for _geo in _geos:
            _shp = to_shp(_geo, catch=True)
            if not _shp:
                continue
            self._check_geo(_geo)

    def _check_geo(self, geo):
        """Apply check to the given geo.

        Args:
            geo (str): transform of mesh to check
        """
        self.write_log(' - checking geo %s', geo)

        # Check create MFnMesh object
        try:
            _mesh = pom.CMesh(geo)
        except ValueError:
            _msg = 'Geo {} failed to build into MFnMesh node'.format(geo)
            self.add_fail(_msg, node=geo)
            return

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
            _plug = _mesh.shp.plug[_attr]
            if _plug.get_val() != _val:
                _msg = 'Bad render setting: "{}" set to "{}"'.format(
                    _plug, {True: 'on', False: 'off'}[_plug.get_val()])
                _fix = wrap_fn(_plug.set_val, _val)
                self.add_fail(_msg, fix=_fix, node=_mesh)


class CheckUVs(SCMayaCheck):
    """Check UVs on current scene geo."""

    task_filter = 'model rig'
    _label = 'Check UVs'

    # sort = 100

    def run(self):
        """Run this check."""
        _geos = sanity_check.read_cache_set('geo')
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
                _fix = wrap_fn(_fix_uvs, geo)
                self.add_fail(_msg, node=geo, fix=_fix)
            else:
                _msg = ('Geo {} does not have uv set map1 (set is '
                        '{})'.format(geo, _set))
                _fix = wrap_fn(_fix_uvs, geo)
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
                _fix = wrap_fn(_fix_uvs, geo)
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
            _fix = wrap_fn(_fix_uvs, geo)
            self.add_fail(_msg, node=geo, fix=_fix)


def _fix_uvs(geo):
    """Clean up sets.

    All unused uvs sets are deleted and the current one is renamed to map1.

    Args:
        geo (str): geometry to clean
    """
    _LOGGER.debug('FIX UVS %s', geo)

    _cur = single(cmds.polyUVSet(geo, query=True, currentUVSet=True))
    _LOGGER.debug(' - CUR %s', _cur)

    # Make sure current is map1
    if _cur != 'map1':
        _LOGGER.debug(' - COPY CURRENT SET %s -> map1', _cur)
        cmds.polyUVSet(geo, uvSet=_cur, newUVSet='map1', copy=True)
        cmds.polyUVSet(geo, uvSet='map1', currentUVSet=True)
        _cur = single(cmds.polyUVSet(geo, query=True, currentUVSet=True))
    assert _cur == 'map1'

    _sets = cmds.polyUVSet(geo, query=True, allUVSets=True)
    _LOGGER.debug(' - SETS %s', _sets)

    # Make sure current set has values (area)
    if not cmds.polyEvaluate(geo, uvArea=True, uvSetName='map1'):
        _set = single([
            _set for _set in _sets
            if cmds.polyEvaluate(geo, uvArea=True, uvSetName=_set)],
            catch=True)
        if _set:
            _LOGGER.debug(' - SET map1 HAS NO AREA -> USING %s', _set)
            cmds.polyUVSet(geo, uvSet=_set, newUVSet='map1', copy=True)

    # Make sure default (first) set is map1
    if len(_sets) > 1 and not _sets[0] == 'map1':
        cmds.polyUVSet(geo, reorder=True, uvSet='map1', newUVSet=_sets[0])
        _sets = cmds.polyUVSet(geo, query=True, allUVSets=True)
        _LOGGER.debug(' - REORDERED %s', _sets)
    assert _sets[0] == 'map1'

    # Remove unused
    if len(_sets) > 1:
        for _set in _sets:
            if _set == 'map1':
                continue
            _LOGGER.debug(' - REMOVE UNUSED %s', _set)
            try:
                cmds.polyUVSet(geo, delete=True, uvSet=_set)
            except RuntimeError as _exc:
                _LOGGER.error(
                    ' - FAILED TO REMOVE %s (error=%s)', _set,
                    str(_exc).strip())
        _sets = cmds.polyUVSet(geo, query=True, allUVSets=True)
        _LOGGER.debug(' - REMOVED UNUSED remaining=%s', _sets)


class CheckGeoNaming(SCMayaCheck):
    """Check naming of cache set geometry."""

    task_filter = 'model rig layout'
    _ignore_names = None

    # Should happen late as renames geo
    sort = 90

    def run(self):
        """Run this check."""

        _geos = _cache_set_to_geos()
        self.write_log('GEOS %s', _geos)
        _names = self._check_geos(geos=_geos)
        self._check_for_duplicates(names=_names)

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

            # Check for duplicate
            _name = to_clean(_geo)
            _names[_name].append(_geo)

        return _names

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
                _msg, _fix, _suggestion = _fix_node_suffix(
                    node=_grp, suffix='_GRP', alts=['_Grp'], type_='group',
                    ignore=self._ignore_names)
                self._ignore_names.append(_suggestion)
                self.add_fail(_msg, node=geo, fix=_fix)
            return
        _geo_s = single(_geo_ss)
        self.write_log('   - shape %s', _geo_s)

        # Check geo name
        if not (geo.endswith('_GEO') or geo == 'GEO'):
            _msg, _fix, _suggestion = _fix_node_suffix(
                node=geo, suffix='_GEO', alts=['_Geo'], type_='geo',
                ignore=self._ignore_names)
            self._ignore_names.append(_suggestion)
            self.add_fail(_msg, node=geo, fix=_fix)
            return

        # Check shape name
        _shp_c = pom.CNode(_geo_s)
        _cur_name = _geo_s.split('|')[-1]
        _good_name = geo.split('|')[-1]+'Shape'
        self.write_log(
            '   - good name %s instanced=%d', _good_name,
            _shp_c.is_instanced())
        if not _shp_c.is_instanced() and _cur_name != _good_name:
            _msg = ('Geo {} does not have matching shape name {} (shape '
                    'is currently {})'.format(geo, _good_name, _geo_s))
            _fix = wrap_fn(self.fix_bad_shape, _geo_s, _good_name)
            self.add_fail(_msg, fix=_fix, node=geo)
            return

    def _check_for_duplicates(self, names):
        """Flag for duplicate nodes in the cache set.

        Args:
            names (dict): name/nodes data
        """
        for _name, _geos in names.items():
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

    def fix_bad_shape(self, shp, name):
        """Fix bad shape name.

        Args:
            shp (str): shape to fix
            name (str): new name to apply
        """
        _LOGGER.debug('FIX BAD SHAPE %s -> %s', shp, name)
        cmds.rename(shp, name)

    def fix_duplicate_nodes(self, nodes):
        """Fix duplicate nodes.

        Args:
            nodes (str): duplicate nodes to fix
        """
        _name = nodes[0].split('|')[-1]
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
            cmds.rename(_node, _new_name)


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

    def run(self):
        """Run this check."""
        _geos = _cache_set_to_geos(shapes=True)
        if not _geos:
            self.add_fail('No geo found')
        for _geo in qt.progress_bar(_geos):

            self.write_log('Checking %s', _geo)

            # Ignore nodes with blendShape
            _hist = cmds.listHistory(
                _geo, pruneDagObjects=True, interestLevel=2) or []
            _blend = [_node for _node in _hist
                      if cmds.objectType(_node) == 'blendShape']
            if _blend:
                continue

            # If skin cluster, check has more than one joint input
            _skin = single(
                cmds.listConnections(
                    _geo, type='skinCluster', destination=False) or [],
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
                'memory issues'.format(_geo))
            self.add_fail(_msg, node=_geo)


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
            _nodes = cmds.namespaceInfo(_ns, listOnlyDependencyNodes=True)
            if _nodes:
                self.write_log('Allowed namespace with nodes %s', _ns)
                continue
            _fix = wrap_fn(del_namespace, _ns)
            self.write_log('Found empty namespace %s', _ns)
            self.add_fail('Empty namespace {}'.format(_ns), fix=_fix)


class NoObjectsWithDefaultShader(SCMayaCheck):
    """Lookdev check to make sure no geos have default shader assigned."""

    task_filter = 'lookdev'

    def run(self):
        """Run this check."""
        _shds = lookdev.read_shader_assignments()

        for _shd, _data in _shds.items():

            _se = _data['shadingEngine']
            _geos = _data['geos']

            # Check for default shader
            if _shd in DEFAULT_NODES:
                for _geo in _geos:
                    _msg = 'Geo "{}" has default shader "{}" applied'.format(
                        _geo, _shd)
                    self.add_fail(_msg, node=_geo)

            # Check for default shading group
            if _se in DEFAULT_NODES:
                for _geo in _geos:
                    _msg = (
                        'Geo "{}" has shader "{}" applied which uses default '
                        'shading engine "{}" - this will cause issues as '
                        'default nodes do not appear in references'.format(
                            _geo, _shd, _se))
                    self.add_fail(_msg, node=_geo)


def _shd_is_arnold(shd, engine, type_):
    """Test whether the given shader is arnold.

    Args:
        shd (str): shader
        engine (str): shading engine
        type_ (str): shader type

    Returns:
        (bool): whether arnold
    """
    _ai_ss_plug = pom.CNode(engine).plug['aiSurfaceShader']
    _ai_ss = _ai_ss_plug.find_incoming(plugs=False)
    if _ai_ss:
        return False
    return not type_.startswith('ai')


class CheckShaders(SCMayaCheck):
    """Check the shader name matches the shading engine.

    eg. myShader -> myShaderSE
    """

    sort = 100
    task_filter = 'lookdev model rig'

    def run(self, check_ai_shd=True):
        """Run this check.

        Args:
            check_ai_shd (bool): check any attached arnold shader override
        """
        _shds = lookdev.read_shader_assignments(
            catch=True, allow_face_assign=True)
        _ren = cmds.getAttr('defaultRenderGlobals.currentRenderer')

        # Check for referenced shaders
        if not _shds and lookdev.read_shader_assignments(allow_referenced=True):
            self.add_fail(
                'Shaders are referenced - this is not supported')

        _ignore_names = set()
        for _shd, _data in _shds.items():

            self.write_log('Checking shader %s', _shd)

            if _shd == 'lambert1':
                continue

            _se = _data['shadingEngine']
            self.write_log(' - shading engine %s', _se)
            _geos = _data['geos']
            _type = cmds.objectType(_shd)

            # Flag namespace
            if _shd != to_clean(_shd):
                _msg = 'Shader {} is using a namespace'.format(_shd)
                _fix = wrap_fn(cmds.rename, _shd, to_clean(_shd))
                self.add_fail(_msg, fix=_fix, node=_shd)
                continue

            # Flag missing MTL suffix
            if not _shd.endswith('_MTL'):
                _msg, _fix, _suggestion = _fix_node_suffix(
                    _shd, suffix='_MTL', alts=['_shd', '_mtl', '_SHD', '_Mat'],
                    type_='shader', ignore=_ignore_names)
                _ignore_names.add(_suggestion)
                self.add_fail(_msg, fix=_fix, node=_shd)
                continue
            _base = _shd[:-4]
            self._check_engine_name(shd=_shd, engine=_se)

            if _ren == 'arnold':

                # Flag non-arnold shader
                if _shd_is_arnold(shd=_shd, engine=_se, type_=_type):
                    _msg = 'Shader {} ({}) is not arnold shader'.format(
                        _shd, _type)
                    self.add_fail(_msg, node=_shd)
                    continue

                # Check ai shader suffix
                _ai_shd = _data.get('ai_shd')
                if check_ai_shd and _ai_shd:
                    if not _ai_shd.endswith('_AIS'):
                        _msg, _fix, _suggestion = _fix_node_suffix(
                            _ai_shd, suffix='_AIS',
                            alts=['_shd', '_mtl', '_SHD'],
                            type_='ai shader', base=_base, ignore=_ignore_names)
                        _ignore_names.add(_suggestion)
                        self.add_fail(_msg, fix=_fix, node=_ai_shd)

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


class CheckForFaceAssignments(SCMayaCheck):
    """Checks for shaders assigned to faces rather than geometry."""

    task_filter = 'lookdev'

    def run(self):
        """Run this check."""
        for _se in cmds.ls(type='shadingEngine'):
            self.write_log('Checking %s', _se)
            _mtl = single(
                cmds.listConnections(_se+'.surfaceShader') or [],
                catch=True)
            if not _mtl:
                self.write_log(' - no surface shader %s', _se)
            _assigns = cmds.sets(_se, query=True) or []
            for _assign in _assigns:
                self.write_log(' - checking assignment %s', _se)
                if '.f' not in _assign:
                    continue
                _msg = '{} has face assigment: {}'.format(_mtl, _assign)
                _fix = wrap_fn(
                    self._fix_face_assignment, engine=_se, assign=_assign)
                self.add_fail(_msg, node=_mtl, fix=_fix)

    def _fix_face_assignment(self, engine, assign):
        """Fix shader face assignment.

        Args:
            engine (str): shading engine
            assign (str): face assignment (eg. body.f[0:100])
        """
        _LOGGER.info('FIX FACE ASSIGNMENTS %s %s', engine, assign)
        assert '.f' in assign
        _node, _ = assign.split('.')
        cmds.sets(assign, edit=True, remove=engine)
        cmds.sets(_node, edit=True, add=engine)
