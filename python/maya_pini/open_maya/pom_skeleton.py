"""Tools for managing skeletons."""

# pylint: disable=not-an-iterable

import logging
import operator
import os
import re
import time

from maya import cmds

from pini import dcc, qt
from pini.utils import (
    single, cache_property, basic_repr, passes_filter, File, cache_result,
    EMPTY)

from maya_pini.utils import to_clean, bake_results, to_namespace, to_node

_LOGGER = logging.getLogger(__name__)
_NAME_MAPPINGS_YML = os.environ.get('MAYA_PINI_SKELETON_NAMES')
if _NAME_MAPPINGS_YML:
    _NAME_MAPPINGS_YML = File(_NAME_MAPPINGS_YML)


class CSkeleton:  # pylint: disable=too-many-public-methods
    """Represents a skeleton consisting of a number of joints."""

    def __init__(self, root):
        """Constructor.

        Args:
            root (CTransform): skeleton root joint
        """
        from maya_pini import open_maya as pom
        self.root = pom.CJoint(root)
        self.namespace = self.root.namespace

    @property
    def anim(self):
        """Find any animation applied to this skeleton.

        Returns:
            (CAnimCurve list): animation curve nodes
        """
        return [_plug.anim for _plug in self.plugs]

    @property
    def name(self):
        """Obtain name for this skeleton.

        This relies on $MAYA_PINI_SKELETON_NAMES yml file being set up. If a
        name hasn't been allocated, the user is asked to allocate one.

        Returns:
            (str): skeleton name
        """
        return self._read_name()

    @property
    def plugs(self):
        """Obtain list of animation plugs for this skeleton.

        This is the transform plugs on the root and the rotation plugs
        on all joints.

        Returns:
            (CPlug list): animation plugs
        """
        _plugs = [self.root.tx, self.root.ty, self.root.tz]
        for _jnt in self.joints:
            _plugs += [_jnt.rx, _jnt.ry, _jnt.rz]
        return tuple(_plugs)

    @property
    def ref(self):
        """Obtain this skeleton's reference.

        Returns:
            (CReference): parent reference
        """
        from maya_pini import open_maya as pom
        return pom.find_ref(self.namespace)

    @cache_property
    def joints(self):
        """Obtain list of joints in this skeleton.

        Returns:
            (CTransform list): joints (starting with root)
        """
        return tuple(self.find_joints())

    @property
    def uid_str(self):
        """Get unique identifier for this skeleton.

        This is all the joint names (without namespace) in path order,
        separated by commas for readability.

        Returns:
            (str): identifier
        """
        return ','.join([_jnt.clean_name for _jnt in self.joints])

    def add_to_grp(self, grp):
        """Add root joint to the given group.

        Args:
            grp (str): group to add root to
        """
        return self.root.add_to_grp(grp)

    def bake(self, range_=None, simulation=True, add_offs=None):
        """Bake animation onto this skeleton.

        Args:
            range_ (tuple): override start/end frames
            simulation (bool): bake as simulation (slow but normally required)
            add_offs (CNode): node to add anim offset/mult chans to
        """
        _LOGGER.debug('BAKE RESULTS')
        _rng = range_ or dcc.t_range()
        _LOGGER.debug(' - RNG %s', _rng)
        _start = time.time()
        _LOGGER.debug(' - PLUGS %s', self.plugs)
        bake_results(self.plugs, range_=_rng, euler_filter=True,
                     simulation=simulation, add_offs=add_offs)
        _LOGGER.debug(' - BAKED RESULTS IN %.01fs', time.time() - _start)

    def bind_to(self, skel, mode='constrain', translate=True, filter_=None):
        """This skeleton to another one.

        ie. this skeleton will be driven by the skeleton provided.

        Args:
            skel (CSkeleton): driver skeleton
            mode (str): how to connect joints
                constrain - use constraints
                connect - use direct connections
            translate (bool): connect translation on root
            filter_ (str): filter the list of joints to bind
        """
        from maya_pini import open_maya as pom
        _LOGGER.debug('BIND %s -> %s', self, skel)

        # Find connections to make
        _to_connect = []
        for _tgl, _trg_jnts, _cons_fn, _attr in [
                (translate, [self.root], pom.CMDS.pointConstraint, 't'),
                (True, self.joints, pom.CMDS.orientConstraint, 'r'),
        ]:
            if not _tgl:
                continue
            for _trg_jnt in _trg_jnts:
                _LOGGER.debug(' - BINDING %s', _trg_jnt)
                if filter_ and not passes_filter(_trg_jnt.clean_name, filter_):
                    continue
                _src_jnt = skel.to_joint(_trg_jnt)
                _LOGGER.debug('   - TARGET %s', _src_jnt)
                if not _src_jnt:
                    raise RuntimeError(
                        f'Target skeleton {skel} is missing joint '
                        f'{_trg_jnt.clean_name}')
                _to_connect.append((_src_jnt, _trg_jnt, _cons_fn, _attr))

        # Build connections
        _cnts = []
        for _src_jnt, _trg_jnt, _cons_fn, _attr in _to_connect:
            if mode == 'constrain':
                _cnt = _cons_fn(_src_jnt, _trg_jnt, maintainOffset=True)
                _cnts.append(_cnt)
            elif mode == 'connect':
                for _axis in 'xyz':
                    _chan = _attr + _axis
                    _src_jnt.plug[_chan].connect(_trg_jnt.plug[_chan])
            else:
                raise ValueError(mode)

        return _cnts

    def build_blend(
            self, srcs, blend=None, allow_missing=False,
            interpolation='No Flip'):
        """Setup a blend between the provided sources.

        Args:
            srcs (CSkeleton list): sources to blend between
            blend (CPlug): blend plug to use (if none is passed then one is
                created on top node of this skeleton's reference)
            allow_missing (bool): no error if missing joints
            interpolation (str): interpolation for orient constraint

        Returns:
            (CPlug): blend plug
        """
        from maya_pini import open_maya as pom
        _LOGGER.debug('BUILD BLEND %s -> %s', srcs, blend)
        assert len(srcs) > 1

        # Get blend + blend inverse
        _blend = blend
        if not _blend:
            _ref = self.to_ref()
            _blend = _ref.top_node.add_attr(
                'blend', 0.0, min_val=0, max_val=len(srcs) - 1)
        _tfm = _blend.node

        # Build blend weight attrs
        _blend_ws = []
        for _idx in range(len(srcs)):
            _blend_w = _tfm.add_attr(
                f'blend_w{_idx}', 0.0, min_val=0, max_val=1)
            for _driver_val, _val in [
                    (_idx - 1, 0),
                    (_idx, 1),
                    (_idx + 1, 0),
            ]:
                cmds.setDrivenKeyframe(
                    _blend_w, currentDriver=_blend, value=_val,
                    driverValue=_driver_val, inTangentType='linear',
                    outTangentType='linear')
            _blend_ws.append(_blend_w)

        # Build constraints
        for _b_jnts, _cons_fn in [
                ([self.root], pom.CMDS.pointConstraint),
                (self.joints, pom.CMDS.orientConstraint),
        ]:
            for _b_jnt in _b_jnts:

                # Build constraint
                _src_jnts = list(filter(bool, [
                    _src.to_joint(_b_jnt) for _src in srcs]))
                if allow_missing and not _src_jnts:
                    continue
                assert _src_jnts
                _args = _src_jnts + [_b_jnt]
                _LOGGER.debug(
                    ' - BUILD CONSTRAINT %s %s -> %s (%d)', _cons_fn,
                    _src_jnts, _b_jnt, _cons_fn is pom.CMDS.orientConstraint)
                _cons = _cons_fn(*_args)
                _type = _cons.object_type()
                _LOGGER.debug(' - TYPE %s', _type)
                if _type == 'orientConstraint':
                    _cons.plug['interpType'].set_enum(interpolation)

                # Connect weights
                for _idx, _blend_w in enumerate(_blend_ws):
                    _blend_w.connect(_cons.plug[f'w{_idx:d}'])

        self.set_col('red')

        return _blend

    def build_hik(self, **kwargs):
        """Build HIK on this skeleton.

        Returns:
            (PHIKNode): HIK system
        """
        from maya_pini import hik
        return hik.build_hik(self, **kwargs)

    def duplicate(self):
        """Duplicate this skeleton.

        Returns:
            (CSkeleton): duplicate skeleton
        """
        _dup = self.root.duplicate()
        return CSkeleton(_dup)

    def find_joint(self, name, side=None, catch=True):
        """Find a joint in this skeleton.

        Args:
            name (str): match by joint name
            side (str): filter by joint side (L/R)
            catch (bool): no error of no joint found

        Returns:
            (CJoint): matching joint
        """
        _LOGGER.debug('FIND JOINT %s side=%s %s', name, side, self)
        _jnts = self.joints
        _LOGGER.debug(' - JNTS %s', _jnts)

        # Apply side filter
        _side = {
            'left': 'L',
            'right': 'R'
        }.get(side.lower() if side else None, side)
        if _side in ('L', 'R', 'C'):
            _jnts = [_jnt for _jnt in _jnts if _jnt.side == _side]
        elif side is None:
            pass
        else:
            raise ValueError(_side)
        _LOGGER.debug(' - SIDE FILTERED %s %s', _side, _jnts)

        # Try match suffix
        _suffix_jnt = single([
            _jnt for _jnt in _jnts if str(_jnt).endswith(name)], catch=True)
        if _suffix_jnt:
            return _suffix_jnt
        _LOGGER.debug(' - SUFFIX FAILED')

        # Try match by side-split
        _ss_jnts = [
            (_jnt, re.split('left|right', str(_jnt).lower())[-1])
            for _jnt in _jnts]
        _LOGGER.debug(' - SS JOINTS %s', _ss_jnts)
        _ss_jnt = single([
            _jnt for _jnt, _ss in _ss_jnts if _ss == name.lower()], catch=True)
        if _ss_jnt:
            return _ss_jnt

        _LOGGER.debug(' - FAILED %s', _jnts)
        if catch:
            return None
        raise ValueError(name)

    def find_joints(self):
        """Find joints in this skeleton.

        Returns:
            (CJoint list): joints
        """
        _jnts = [self.root] + self.root.cmds.listRelatives(
            allDescendents=True, type='joint')
        _jnts.sort(key=operator.methodcaller('to_long'))
        assert _jnts[0] == self.root
        return _jnts

    def hide(self):
        """Hide this skeleton via its root."""
        self.root.hide()

    def loop(self):
        """Loop this skeleton's animation."""
        for _plug in self.plugs:
            _offset = _plug.attr in ['tx', 'tz']
            if not _plug.anim:
                continue
            _plug.anim.loop(offset=_offset)

    def to_joint(self, name, catch=True):
        """Find a joint in this skeleton.

        Args:
            name (str): match by name
            catch (bool): no error if no joint found

        Returns:
            (CJoint): joint
        """
        from maya_pini import open_maya as pom
        _LOGGER.debug('TO JOINT %s', name)

        # Try simple name match
        _name = to_clean(name)
        _node = to_node(_name, namespace=self.namespace)
        _LOGGER.debug(' - NODE %s', _node)
        if cmds.objExists(_node):
            return pom.CJoint(_node)
        _LOGGER.debug(' - NODE DOES NOT EXIST')

        if not catch:
            raise ValueError(name)
        return None

    def to_ref(self):
        """Find this skeleton's associated reference.

        Returns:
            (FileRef): reference
        """
        from maya_pini import open_maya as pom
        return pom.find_ref(self.namespace)

    def _read_name(self):
        """Read name of this skeleton.

        This relies on $MAYA_PINI_SKELETON_NAMES being set up.

        Returns:
            (str): skeleton name
        """
        _mappings = _read_name_mappings()
        if self.uid_str not in _mappings:
            _LOGGER.info(' - NAMES %s', list(_mappings.values()))
            _name = qt.input_dialog(
                'Enter name for this skeleton:',
                title='Skeleton Naming')
            assert _name not in _mappings.keys()
            _mappings[self.uid_str] = _name
            _NAME_MAPPINGS_YML.write_yml(_mappings)
            _mappings = _read_name_mappings(force=True)
            assert self.uid_str in _mappings
        return _mappings[self.uid_str]

    def set_col(self, col):
        """Set colour of this skeleton.

        Args:
            col (str): colour to apply (eg. red/green/blue)
        """
        for _jnt in self.joints:
            _jnt.set_col(col)

    def set_joint_radius(self, radius):
        """Set radius for all joints.

        Args:
            radius (float): radius to apply
        """
        for _jnt in self.joints:
            _jnt.plug['radius'].set_val(radius)

    def t_dur(self):
        """Obtain this skeleton's animation's timeline duration.

        Returns:
            (float): duration (in frames)
        """
        return self.root.tx.t_dur()

    def t_offset(self, offset):
        """Apply a time offset to this skeleton's animation curves.

        Args:
            offset (float): offset to apply (in frames)
        """
        for _plug in self.plugs:
            _plug.t_offset(offset)

    def t_range(self, class_=float):
        """Determine animation range.

        Args:
            class_ (class): override class of result

        Returns:
            (tuple): start/end frames
        """
        return self.root.tx.t_range(class_=class_)

    def unhide(self):
        """Show this skelton via its root joint."""
        self.root.unhide()

    def to_name(self, catch=True):
        """Obtain name assigned to this skeleton.

        Args:
            catch (bool): no error if no name assigned

        Returns:
            (str): skeleton name
        """
        try:
            return self._read_name()
        except RuntimeError as _exc:
            if catch:
                return None
            raise _exc

    def zero(self, break_conns=False):
        """Zero out this skeleton.

        Args:
            break_conns (bool): break connections
        """
        for _jnt in self.joints:
            for _plug in [_jnt.rx, _jnt.ry, _jnt.rz]:
                if _plug.is_locked():
                    continue
                _plug.set_val(0)
                if break_conns:
                    _plug.break_conns()

    def __repr__(self):
        return basic_repr(self, str(self.root), separator='|')


def find_skeleton(match=None, namespace=EMPTY, referenced=None, catch=False):
    """Find a skeleton in the current scene.

    Args:
        match (str): match by filter or namespace
        namespace (str): filter by namespace
        referenced (bool): filter by referenced status
        catch (bool): no error if exactly one skeleton not found

    Returns:
        (CSkeleton): matching skeleton
    """
    _LOGGER.debug('FIND SKELETON')
    _skels = find_skeletons(namespace=namespace, referenced=referenced)
    _LOGGER.debug(' - MATCHED %d SKELS %s', len(_skels), _skels)

    if not match and len(_skels) == 1:
        return single(_skels)

    _ns_matches = [_skel for _skel in _skels if _skel.namespace == match]
    if len(_ns_matches) == 1:
        return single(_ns_matches)

    _root_matches = [_skel for _skel in _skels if _skel.root == match]
    if len(_root_matches) == 1:
        return single(_root_matches)

    # Try match as namespace filter
    _ns_filter_matches = [
        _skel for _skel in _skels
        if _skel.namespace and
        passes_filter(_skel.namespace, match)]
    if len(_ns_filter_matches) == 1:
        return single(_ns_filter_matches)

    # Try root namespace match
    _root_ns_matches = [
        _skel for _skel in _skels
        if _skel.namespace == match or
        (_skel.namespace and _skel.namespace.split(':')[0] == match)]
    if len(_root_ns_matches) == 1:
        return single(_root_ns_matches)

    if catch:
        return None
    raise ValueError(f'Failed to find skeleton {match or namespace}')


def find_skeletons(namespace=EMPTY, filter_=None, referenced=None):
    """Find skeletons in the current scene.

    Args:
        namespace (str): filter by exact namespace
        filter_ (str): apply namespace filter
        referenced (bool): filter by referenced status

    Returns:
        (CSkeleton list): matching skeletons
    """
    _skels = []
    for _skel in _read_skeletons():
        if namespace is not EMPTY and _skel.namespace != namespace:
            continue
        if not passes_filter(_skel.namespace, filter_):
            continue
        if referenced is not None and _skel.root.is_referenced() != referenced:
            continue
        _skels.append(_skel)
    return _skels


def _read_skeletons():
    """Read skeletons in the current scene.

    Returns:
        (CSkeleton list): skeletons
    """
    from maya_pini import open_maya as pom

    _skels = []
    for _jnt in pom.CMDS.ls(type='joint'):
        _parent = _jnt.to_parent()
        if _parent and _parent.object_type() == 'joint':
            continue
        _skel = CSkeleton(_jnt)
        _skels.append(_skel)

    return _skels


@cache_result
def _read_name_mappings(force=False):
    """Read name mappings yml file.

    Args:
        force (bool): force reread from disk

    Returns:
        (dict): skeleton names
    """
    if not _NAME_MAPPINGS_YML:
        raise RuntimeError(
            'No name mapping found - $MAYA_PINI_SKELETON_NAMES not set')
    return _NAME_MAPPINGS_YML.read_yml(catch=True)


def selected_skeleton():
    """Read selected skeleton.

    Returns:
        (CSkeleton): selected skeleton
    """
    _nss = {to_namespace(_node)
            for _node in cmds.ls(selection=True) or []}
    _ns = single(_nss)
    return find_skeleton(namespace=_ns)
