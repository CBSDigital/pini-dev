"""Maya rig checks."""

import logging

from maya import cmds

from pini import pipe
from pini.utils import single, wrap_fn, check_heart

from maya_pini import open_maya as pom, m_pipe
from maya_pini.utils import to_clean

from .. import core, utils
from . import scc_maya, scc_maya_asset

_LOGGER = logging.getLogger(__name__)


class CheckCtrlsSet(core.SCMayaCheck):
    """Check rig has controls set."""

    task_filter = 'rig'
    depends_on = (scc_maya.CheckForNamespace, )

    def run(self):
        """Run this check."""

        # Check for set
        _name = m_pipe.find_ctrls_set(mode='name')
        if not cmds.objExists(_name):
            _fix = wrap_fn(cmds.sets, name=_name, empty=True)
            self.add_fail(f'Missing ctrls set "{_name}"', fix=_fix)
            return

        self.set = pom.CNode(_name)
        _type = self.set.object_type()
        self.write_log('Found set %s %s', self.set, _type)
        if _type != 'objectSet':
            self.add_fail('Bad ctrls set "{_name}" type "{_type}"')
            return
        self.ctrls = cmds.sets(self.set, query=True) or []
        self.write_log('Found %d nodes', len(self.ctrls))
        if not self.ctrls:
            self.add_fail(
                f'The controls set "{_name}" is empty - please add your rig '
                'controls to this set by middle-mouse dragging the nodes '
                'in the outliner into it', node=self.set)
            return
        self.write_log('Checked set %s %s', _name, self.set)

        self._check_ctrls_for_namespace()

    def _check_ctrls_for_namespace(self):
        """Flag controls using namespace.

        This is disabled if this asset has already been published to avoid
        losing animation in scenes using old versions of a rig.
        """
        self.write_log('check ctrls for namespace')
        _work = pipe.CACHE.obt_cur_work()
        _pubs = _work.work_dir.find_outputs(type_='publish', tag=_work.tag)
        if _pubs:
            self.write_log(' - disabled as publishes found')
            return
        for _ctrl in self.ctrls:
            _ctrl = pom.cast_node(_ctrl)
            if _ctrl.is_referenced():
                continue
            if not _ctrl.namespace:
                continue
            _msg = f'Control "{_ctrl}" is using a namespace'
            _fix = None
            if not _ctrl.is_referenced():
                _fix = wrap_fn(cmds.rename, _ctrl, to_clean(_ctrl))
            self.add_fail(_msg, fix=_fix, node=_ctrl)


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
    action_filter = 'RigPublish'
    depends_on = (scc_maya_asset.CheckCacheSet, )

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
                f'Mesh "{_geo.shp}" has a skin cluster with no blendShape '
                f'and a single input joint. This can cause bloat in abcs '
                'because skin clusters cause every vertex to be exported '
                'on every frame (as if they are deforming), making for '
                'large files and slow caching. It would better to use a '
                'constraint or parenting to build the rig.')
            self.add_fail(_msg, node=_geo.shp)


class CheckBlendshapes(core.SCMayaCheck):
    """Check for unused blendshapes."""

    task_filter = 'rig'

    def run(self):
        """Run this check."""
        for _bs in pom.find_nodes(type_='blendShape'):

            self.write_log('blendshape %s', _bs)

            _aliases_l = cmds.aliasAttr(_bs, query=True) or []
            _aliases = {
                _aliases_l[_idx + 1]: _aliases_l[_idx]
                for _idx in range(0, len(_aliases_l), 2)}
            self.write_log(' - aliases %s', _aliases)

            _used = False
            for _attr, _alias in _aliases.items():
                _plug = _bs.plug[_attr]
                _connected = bool(_plug.find_incoming())
                _wt = _plug.get_val()
                _LOGGER.info(
                    '   - CHECK INPUT %s %s con=%d wt=%s', _alias, _plug,
                    _connected, _wt)
                if _connected or _wt:
                    _used = True

            if not _used:
                self.write_log(' - unused')
                self.add_fail(
                    f'Blendshape "{_bs}" has zero weights and no inputs and '
                    f'is effectively doing nothing - if it is not needed it '
                    f'can be deleted scene',
                    fix=wrap_fn(utils.safe_delete, _bs), node=_bs)
