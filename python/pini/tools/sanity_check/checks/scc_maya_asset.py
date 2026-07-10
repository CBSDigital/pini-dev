"""Maya asset checks."""

import os
import logging

from maya import cmds

from pini import pipe
from pini.dcc import export
from pini.utils import single, wrap_fn, plural, check_heart

from maya_pini import ref, open_maya as pom, m_pipe
from maya_pini.utils import (
    DEFAULT_NODES, del_namespace, to_clean, add_to_set, to_long)

from .. import core, utils
from . import scc_maya_lookdev

_LOGGER = logging.getLogger(__name__)


class CheckAssetHierarchy(core.SCMayaCheck):
    """Check scene has a single top node matching a given name."""

    action_filter = 'Publish -LookdevPublish'
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
        _junk_filter = ' '.join(f'-{_grp}' for _grp in m_pipe.JUNK_GRPS)
        _top_node = pom.find_node(
            top_node=True, default=False, filter_=_junk_filter, catch=True)
        if _top_node and to_clean(_top_node) != _req_top_node:
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
            if to_clean(_node) not in [_top_node] + m_pipe.JUNK_GRPS]
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
        _set = m_pipe.find_cache_set()
        if not _set:
            _fix = wrap_fn(cmds.sets, name='cache_SET', empty=True)
            self.add_fail('Missing cache set', fix=_fix)
            return
        if _set.object_type() != 'objectSet':
            self.add_fail('Bad cache set type')
            return

        _geos = m_pipe.read_cache_set(set_=_set, mode='geo')
        _tfms = m_pipe.read_cache_set(set_=_set, mode='tfm')
        self.write_log('Geos %s', _geos)

        # Flag no geo
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

        if self._check_for_referenced_tfm(tfms=_tfms):
            return

        utils.check_cacheable_set(set_=_set, check=self)

    def _check_for_referenced_tfm(self, tfms):
        """Check for referenced export geo.

        Args:
            tfms (CTransform list): cache set transforms

        Returns:
            (bool): whether check failed
        """

        # Check for referenced transforms
        _refd_tfms = [_tfm for _tfm in tfms if _tfm.is_referenced()]
        if not _refd_tfms:
            return False
        self.write_log('Referenced tfms %s', _refd_tfms)
        _refs = sorted({_tfm.to_reference() for _tfm in _refd_tfms})
        self.write_log('Refs %s', _refs)
        assert _refs

        _refs_mode = export.get_pub_refs_mode()
        _imp_root = export.PubRefsMode.IMPORT_TO_ROOT
        _imp_underscores = export.PubRefsMode.IMPORT_USING_UNDERSCORES
        self.write_log('Refs mode %s', _refs_mode)

        if len(_refs) == 1 and _refs_mode != _imp_root:
            _fix = wrap_fn(export.set_pub_refs_mode, _imp_root)
            self.add_fail(
                f'Referenced geo in cache set but references mode is '
                f'set to "{_refs_mode.value}" (should be '
                f'"{_imp_root.value}")',
                fix=_fix)
            return True

        if len(_refs) != 1 and _refs_mode != _imp_underscores:
            _fix = wrap_fn(export.set_pub_refs_mode, _imp_underscores)
            self.add_fail(
                f'Referenced geo from multiple references in cache set '
                f'but references mode is "{_refs_mode.value}" (should be '
                f'"{_imp_root.value}")',
                fix=_fix)
            return True

        return False


class CheckCtrlsSet(core.SCMayaCheck):
    """Check rig has controls set."""

    task_filter = 'rig'

    def run(self):
        """Run this check."""
        _name = m_pipe.find_ctrls_set(mode='name')
        if not cmds.objExists(_name):
            _fix = wrap_fn(cmds.sets, name=_name, empty=True)
            self.add_fail(f'Missing ctrls set "{_name}"', fix=_fix)
            return
        _set = pom.CNode(_name)
        _type = _set.object_type()
        self.write_log('Found set %s %s', _set, _type)
        if _type != 'objectSet':
            self.add_fail('Bad ctrls set "{_name}" type "{_type}"')
            return
        _nodes = cmds.sets(_set, query=True) or []
        self.write_log('Found %d nodes', len(_nodes))
        if not _nodes:
            self.add_fail(f'Empty ctrls set "{_name}" type')
            return
        self.write_log('Checked set %s %s', _name, _set)


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


class CheckForVertexColorSets(core.SCMayaCheck):
    """Check geometry has no vertex colour sets."""

    task_filter = 'model rig'
    depends_on = (CheckCacheSet, )

    def run(self):
        """Run this check."""
        _geos = m_pipe.read_cache_set()
        self.write_log('Found %d geos: %s', len(_geos), _geos)
        for _geo in _geos:
            _vcss = cmds.polyColorSet(_geo, query=True, allColorSets=True)
            if not _vcss:
                continue
            _vcss_s = str(_vcss).strip('[]')
            self.add_fail(
                f'Geo "{_geo} has {len(_vcss)} vertex color sets: {_vcss_s}',
                fix=wrap_fn(_remove_vtx_col_sets, geo=_geo, vcss=_vcss))


def _remove_vtx_col_sets(geo, vcss):
    """Remove vertex colour sets from geo.

    Args:
        geo (CMesh): geo to update
        vcss (str list): colour sets to remove
    """
    _LOGGER.info('REMOVE VTX COL SETS %s %s', geo, vcss)
    for _vcs in vcss:
        cmds.polyColorSet(geo, delete=True, colorSet=_vcs)


class CheckGeoNaming(core.SCMayaCheck):
    """Check naming of cache set geometry."""

    task_filter = 'model rig layout'
    _ignore_names = None
    depends_on = (CheckCacheSet, )

    # Should happen late as renames geo
    sort = 90

    def run(self, set_=None, limit=None):
        """Run this check.

        Args:
            set_ (str): override cache set name
            limit (int): limit the number of geos (for debugging)
        """
        _geos = utils.read_cache_set_geo(set_=set_)
        if limit:
            _geos = _geos[:limit]
        self.write_log('geos %s', _geos)
        self._ignore_names = []
        self._start_idxs = {}
        for _geo in self.update_progress(_geos):
            self._check_geo(_geo)

    def _check_geo(self, geo):
        """Apply check to the given geo.

        Args:
            geo (CMesh): mesh to check
        """
        assert isinstance(geo, pom.CMesh)
        self.write_log(
            ' - checking geo %s ref=%d', geo, geo.is_referenced(), lazy=True)

        # Check for namespace
        _refs_mode = export.get_pub_refs_mode()
        _import = export.PubRefsMode.IMPORT_TO_ROOT
        if geo.namespace and _refs_mode not in (
                export.PubRefsMode.IMPORT_TO_ROOT,
                export.PubRefsMode.IMPORT_USING_UNDERSCORES):
            _clean_name = geo.to_clean()
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
        if not (_name.endswith(f'_{_geo_suffix}') or _name == _geo_suffix):
            _msg, _fix, _suggestion = utils.fix_node_suffix(
                node=geo, suffix='_' + _geo_suffix,
                alts=['_Geo', '_GEO', '_geo', '_geom'], type_='geo',
                ignore=self._ignore_names, start_idxs=self._start_idxs)
            # _LOGGER.info(' - START IDXS %s', self._start_idxs)
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
            if str(_cam).strip('|') in DEFAULT_NODES:
                continue
            self.add_fail(f'Camera {_cam} inside asset hierarchy', node=_cam)


class FindUnneccessarySkinClusters(core.SCMayaCheck):
    """Find skin clusters which are not needed.

    If a skin cluster is used where a constraint can be used, this can
    cause bloat on AbcExport. The exporter sees the skin cluster and
    determines that it needs to export the geo as a point cloud rather
    than just exporting transform information. This means that every
    point position is exported on every frame, which can cause memory
    issues and unnecessarily large abcs.
    """

    task_filter = 'rig'
    action_filter = 'BasicPublish'
    depends_on = (CheckCacheSet, )

    def run(self):
        """Run this check."""

        _geos = utils.read_cache_set_geo()
        if not _geos:
            self.add_fail('No geo found')

        for _geo in self.update_progress(_geos):

            self.write_log('Checking %s', _geo)
            check_heart()

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


class CheckShaders(scc_maya_lookdev.CheckLookdevShaders):
    """Check model shaders."""

    action_filter = 'ModelPublish BasicPublish'
    task_filter = 'model rig'
    depends_on = (CheckGeoNaming, )

    def run(self):
        """Run this check."""
        super().run(
            check_refd_geo=False, shds_required=False, check_ai_shd=False)
