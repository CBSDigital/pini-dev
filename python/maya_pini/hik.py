"""Tools for managing human IK."""

import collections
import logging
import pprint

from pini import pipe, qt
from pini.dcc import pipe_ref
from pini.utils import single, passes_filter, EMPTY

from maya_pini import ui, open_maya as pom
from maya_pini.utils import process_deferred_events, restore_ns, set_namespace

from maya import cmds, mel

_LOGGER = logging.getLogger(__name__)

CHAR_LIST = ui.OptionMenuGrp('hikCharacterList')
SRC_LIST = ui.OptionMenuGrp('hikSourceList')

CONTROL_RIG = 'Control Rig'
STANCE = 'Stance'


class PHIKNode(pom.CNode):
    """Represent an HIKCharacter node."""

    @property
    def properties(self):
        """Obtain properties node.

        Returns:
            (CNode): HIK properties
        """
        return single(self.find_connections(
            type_='HIKProperty2State', plugs=False, connections=False))

    def bake_to_ctrl_rig(self):
        """Bake animation to control rig."""
        raise NotImplementedError

        # _ctrls = {
        #     'Lemon01:Auto_Ctrl_ChestEndEffector.rotate',
        #     'Lemon01:Auto_Ctrl_ChestEndEffector.translate',
        #     'Lemon01:Auto_Ctrl_ChestOriginEffector.rotate',
        #     'Lemon01:Auto_Ctrl_ChestOriginEffector.translate',
        #     'Lemon01:Auto_Ctrl_Head.rotate',
        #     'Lemon01:Auto_Ctrl_HeadEffector.rotate',
        #     'Lemon01:Auto_Ctrl_HeadEffector.translate',
        #     'Lemon01:Auto_Ctrl_Hips.rotate',
        #     'Lemon01:Auto_Ctrl_Hips.translate',
        #     'Lemon01:Auto_Ctrl_HipsEffector.rotate',
        #     'Lemon01:Auto_Ctrl_HipsEffector.translate',
        #     'Lemon01:Auto_Ctrl_LeftAnkleEffector.rotate',
        #     'Lemon01:Auto_Ctrl_LeftAnkleEffector.translate',
        #     'Lemon01:Auto_Ctrl_LeftArm.rotate',
        #     'Lemon01:Auto_Ctrl_LeftElbowEffector.rotate',
        #     'Lemon01:Auto_Ctrl_LeftElbowEffector.translate',
        #     'Lemon01:Auto_Ctrl_LeftFoot.rotate',
        #     'Lemon01:Auto_Ctrl_LeftFootEffector.rotate',
        #     'Lemon01:Auto_Ctrl_LeftFootEffector.translate',
        #     'Lemon01:Auto_Ctrl_LeftForeArm.rotate',
        #     'Lemon01:Auto_Ctrl_LeftHand.rotate',
        #     'Lemon01:Auto_Ctrl_LeftHipEffector.rotate',
        #     'Lemon01:Auto_Ctrl_LeftHipEffector.translate',
        #     'Lemon01:Auto_Ctrl_LeftKneeEffector.rotate',
        #     'Lemon01:Auto_Ctrl_LeftKneeEffector.translate',
        #     'Lemon01:Auto_Ctrl_LeftLeg.rotate',
        #     'Lemon01:Auto_Ctrl_LeftShoulder.rotate',
        #     'Lemon01:Auto_Ctrl_LeftShoulderEffector.rotate',
        #     'Lemon01:Auto_Ctrl_LeftShoulderEffector.translate',
        #     'Lemon01:Auto_Ctrl_LeftToeBase.rotate',
        #     'Lemon01:Auto_Ctrl_LeftUpLeg.rotate',
        #     'Lemon01:Auto_Ctrl_LeftWristEffector.rotate',
        #     'Lemon01:Auto_Ctrl_LeftWristEffector.translate',
        #     'Lemon01:Auto_Ctrl_Neck.rotate',
        #     'Lemon01:Auto_Ctrl_RightAnkleEffector.rotate',
        #     'Lemon01:Auto_Ctrl_RightAnkleEffector.translate',
        #     'Lemon01:Auto_Ctrl_RightArm.rotate',
        #     'Lemon01:Auto_Ctrl_RightElbowEffector.rotate',
        #     'Lemon01:Auto_Ctrl_RightElbowEffector.translate',
        #     'Lemon01:Auto_Ctrl_RightFoot.rotate',
        #     'Lemon01:Auto_Ctrl_RightFootEffector.rotate',
        #     'Lemon01:Auto_Ctrl_RightFootEffector.translate',
        #     'Lemon01:Auto_Ctrl_RightForeArm.rotate',
        #     'Lemon01:Auto_Ctrl_RightHand.rotate',
        #     'Lemon01:Auto_Ctrl_RightHipEffector.rotate',
        #     'Lemon01:Auto_Ctrl_RightHipEffector.translate',
        #     'Lemon01:Auto_Ctrl_RightKneeEffector.rotate',
        #     'Lemon01:Auto_Ctrl_RightKneeEffector.translate',
        #     'Lemon01:Auto_Ctrl_RightLeg.rotate',
        #     'Lemon01:Auto_Ctrl_RightShoulder.rotate',
        #     'Lemon01:Auto_Ctrl_RightShoulderEffector.rotate',
        #     'Lemon01:Auto_Ctrl_RightShoulderEffector.translate',
        #     'Lemon01:Auto_Ctrl_RightToeBase.rotate',
        #     'Lemon01:Auto_Ctrl_RightUpLeg.rotate',
        #     'Lemon01:Auto_Ctrl_RightWristEffector.rotate',
        #     'Lemon01:Auto_Ctrl_RightWristEffector.translate',
        #     'Lemon01:Auto_Ctrl_Spine.rotate',
        #     'Lemon01:Auto_Ctrl_Spine1.rotate',
        #     'Lemon01:Auto_Ctrl_Spine2.rotate',
        #     'Lemon01:Auto_Ctrl_Spine3.rotate',
        #  }

        # cmds.bakeResults(
        #     simulation=True, -t "0:34.4" -sampleBy 1 -oversamplingRate 1
        #     disableImplicitControl true -preserveOutsideKeys true
        #     sparseAnimCurveBake false
        #     removeBakedAttributeFromLayer false -
        #     removeBakedAnimFromLayer false -
        #     bakeOnOverrideLayer false -minimizeRotation true -
        #     controlPoints false -shape true

    def bake_to_skel(
            self, range_=None, step=None, loop=False, skel=None,
            euler_filter=True, force=False):
        """Bake animation to skeleton.

        Args:
            range_ (tuple): override range (otherwise read from anim)
            step (float): override step size (otherwise read from anim)
            loop (bool): apply looping
            skel (CSkeleton): skeleton to bake to
            euler_filter (bool): apply euler filter
            force (bool): supress any bake warnings
        """
        _LOGGER.info('BAKE TO SKEL %s', self)
        _skel = skel or self.to_skel()
        _LOGGER.info(' - SKEL %s', _skel)

        # Read range + step size from source anim
        _rng = range_
        _step = step
        if not _rng or not step:
            _src_skel = pom.find_skeleton(self.get_source().namespace)
            _LOGGER.info(' - SRC SKEL %s', _src_skel)
            _src_root = _src_skel.root
            _LOGGER.info(' - SRC ROOT %s', _src_root)
            _src_ktvs = _src_root.rx.get_ktvs()
            assert _src_ktvs
            _src_keys = [_time for _time, _ in _src_ktvs]
            _LOGGER.info(' - SRC KEYS %s', _src_keys)
            if not _step:
                _step = _read_step_size(_src_keys, force=force)
            if not _rng:
                _rng = _src_keys[0], _src_keys[-1]
        _LOGGER.info(' - RANGE / STEP %s %s', _rng, _step)

        # Bake anim (copied from HIK bake to skeleton)
        _plugs = [_skel.root.translate]
        _plugs += [_jnt.rotate for _jnt in _skel.joints]
        _LOGGER.info(' - PLUGS %s', _plugs)
        mel.eval(f'hikBakeCharacterPre "{self}"')
        cmds.bakeResults(
            _plugs, simulation=True, time=_rng, sampleBy=_step,
            oversamplingRate=1, disableImplicitControl=True,
            preserveOutsideKeys=True, sparseAnimCurveBake=False,
            removeBakedAttributeFromLayer=False,
            removeBakedAnimFromLayer=False, bakeOnOverrideLayer=False,
            minimizeRotation=True, controlPoints=False, shape=True)
        mel.eval(f'hikBakeCharacterPost "{self}"')
        cmds.DeleteStaticChannels()
        if euler_filter:
            cmds.filterCurve(_plugs)

        # Apply looping
        if loop:
            _LOGGER.debug(' - APPLY LOOP %s', loop)
            if loop == 'Path':
                _offs_trgs = [_skel.root.tz]
            elif loop in (True, 'Loopable'):
                _offs_trgs = []
            else:
                raise ValueError(loop)
            for _crv in pom.find_anims(
                    namespace=self.namespace, referenced=False):
                _LOGGER.debug(' - CURVE %s', _crv)
                if not _crv.output.find_connections():
                    _LOGGER.debug('   - DELETE UNCONNECTED')
                    _crv.delete()
                    continue
                _offs = _crv.target in _offs_trgs
                _LOGGER.debug('   - OFFS %s', _offs)
                _crv.loop(offset=_offs)

    def get_source(self):
        """Obtain source for this HIK node.

        Returns:
            (None|str|PHIKNode): source (HIK, control rig or None)
        """
        _LOGGER.debug('GET SOURCE %s', self)

        self.set_current()

        _src = SRC_LIST.get_val().strip()
        _LOGGER.info(' - SOURCE %s = %s', self, _src)
        if _src == CONTROL_RIG:
            _result = CONTROL_RIG
        elif _src == STANCE:
            _result = STANCE
        elif _src == 'None':
            _result = None
        elif cmds.objExists(_src):
            _result = PHIKNode(_src)
        else:
            raise ValueError(_src)
        return _result

    def set_source(self, source):
        """Set HIK source for this node.

        Args:
            source (str|PHIKNode): source to apply
                None - set source to node
                CONTROL_RIG - apply control rig
                HIK node - apply HIK source
        """
        _LOGGER.info('SET SOURCE %s -> %s', self, source)

        self.set_current()

        # Find source to select
        _hik = None
        if source in (None, CONTROL_RIG):
            _select = source
        elif isinstance(source, (str, pom.CReference, pom.CNode)):
            _hik = find_hik(source)
            _LOGGER.info(' - HIK %s', _hik)
            _select = _hik
        else:
            raise ValueError(source)

        # Run HIK mel
        process_deferred_events()
        if _hik:
            mel.eval(f'mayaHIKsetCharacterInput("{self}", "{_hik}")')
            process_deferred_events()
            cmds.refresh()
            _LOGGER.debug(' - SELECTED "%s"', SRC_LIST.get_val())

        # Update ui
        _LOGGER.debug(' - SELECT %s', _select)
        SRC_LIST.set_val(f' {_select}', catch=False)
        process_deferred_events()
        cmds.refresh()
        _LOGGER.debug(' - SELECTED "%s"', SRC_LIST.get_val())
        assert SRC_LIST.get_val() == f' {_select}'

    def set_current(self, force=False):
        """Set this HIK as current selection in the ui.

        Args:
            force (bool): run selection scripts even if no change needed
        """
        _LOGGER.debug(' - SET CURRENT "%s"', self)

        process_deferred_events()

        _sel = CHAR_LIST.get_val()
        _LOGGER.debug('   - SELECTED "%s" sel=%d', _sel, _sel == self)
        if _sel == self:
            _LOGGER.debug('   - ALREADY SET TO %s', self)
            return

        # Run HIK mel
        _LOGGER.debug('   - SELECTING %s', self)
        mel.eval(f'hikEnableCharacter("{self}", false)')
        mel.eval(f'hikSetCurrentCharacter {self}')
        mel.eval('hikUpdateSourceList()')

        if not CHAR_LIST.get_val() == self:
            _LOGGER.debug(' - SELECT CHAR %s', self)
            CHAR_LIST.set_val(str(self), catch=True)
            process_deferred_events()

        # assert CHAR_LIST.get_val() == self
        _LOGGER.debug(' - CURRENT CHAR %s', CHAR_LIST.get_val())
        cmds.refresh()

        # CHAR_LIST.select_item(_char)
        process_deferred_events()

        assert CHAR_LIST.get_val() == self

    def to_skel(self):
        """Obtain this HIK system's skeleton.

        Returns:
            (CSkeleton): skeleton
        """
        _root = self.plug['Hips'].find_incoming(plugs=False)
        return pom.CSkeleton(_root)


def _assign_hik_jnt(src, trg, char, mode='connect'):
    """Assign a joint to the an HIK character joint.

    Args:
        src (CJoint): joint to assign
        trg (str): name of HIK joint to connect to
        char (PHIKNode): HIK character to update
        mode (str): how to assign the joint
            legacy - use mel script
            connect - connect the joint.Character attribute to the
                corresponding joint attribute on the node
    """
    _LOGGER.debug('BIND HIK JNT %s -> %s (%s)', src, trg, char)
    if mode == 'legacy':
        _map = [
            'Reference',
            'Hips',

            'LeftUpLeg',
            'LeftLeg',
            'LeftFoot',
            'RightUpLeg',
            'RightLeg',
            'RightFoot',

            'Spine',

            'LeftArm',
            'LeftForeArm',
            'LeftHand',
            'RightArm',
            'RightForeArm',
            'RightHand',

            'Head',
            'LeftToeBase',
            'RightToeBase',
            'LeftShoulder',
            'RightShoulder',
            'Neck',
            '<LeftExtraWrist>',
            '<RightExtraWrist>',

            'Spine1',  # 23
            'Spine2',  # 24
            'Spine3',  # 26
            'Spine4',  # 27
            'Spine5',  # 28
            'Spine6',  # 29
            'Spine7',  # 30
            'Spine8',  # 31
            'Spine9',  # 32

            'Neck1',  # 33
            'Neck2',  # 34
            'Neck3',  # 35
            'Neck4',  # 36
            'Neck5',  # 37
            'Neck6',  # 38
            'Neck7',  # 39
            'Neck8',  # 40
            'Neck9',  # 41
        ]
        _idx = _map.index(trg)
        # _LOGGER.info(' - MAP %s -> %s (%d)', src, trg, _idx)
        if not cmds.objExists(src):
            raise RuntimeError(f'Missing joint {src}')
        _mel = f'setCharacterObject("{src}", "{char}", {_idx:d}, 0)'
        mel.eval(_mel)

        # mel.eval('setCharacterObject("thumb_01_l", "Character1",50,0);')
        # mel.eval('setCharacterObject("thumb_02_l", "Character1",51,0);')
        # mel.eval('setCharacterObject("thumb_03_l", "Character1",52,0);')
        # mel.eval('setCharacterObject("thumb_04_l_Jx", "Character1",53,0);')
        # mel.eval('setCharacterObject("index_01_l", "Character1",54,0);')
        # mel.eval('setCharacterObject("index_02_l", "Character1",55,0);')
        # mel.eval('setCharacterObject("index_03_l", "Character1",56,0);')
        # mel.eval('setCharacterObject("index_04_l_Jx", "Character1",57,0);')
        # mel.eval('setCharacterObject("middle_01_l", "Character1",58,0);')
        # mel.eval('setCharacterObject("middle_02_l", "Character1",59,0);')
        # mel.eval('setCharacterObject("middle_03_l", "Character1",60,0);')
        # mel.eval('setCharacterObject("middle_04_l_Jx", "Character1",61,0);')
        # mel.eval('setCharacterObject("ring_01_l", "Character1",62,0);')
        # mel.eval('setCharacterObject("ring_02_l", "Character1",63,0);')
        # mel.eval('setCharacterObject("ring_03_l", "Character1",64,0);')
        # mel.eval('setCharacterObject("ring_04_l_Jx", "Character1",65,0);')
        # mel.eval('setCharacterObject("pinky_01_l", "Character1",66,0);')
        # mel.eval('setCharacterObject("pinky_02_l", "Character1",67,0);')
        # mel.eval('setCharacterObject("pinky_03_l", "Character1",68,0);')
        # mel.eval('setCharacterObject("pinky_04_l_Jx", "Character1",69,0);')
        # #70-73 is left hand 6th finger
        # mel.eval('setCharacterObject("thumb_01_r", "Character1",74,0);')
        # mel.eval('setCharacterObject("thumb_02_r", "Character1",75,0);')
        # mel.eval('setCharacterObject("thumb_03_r", "Character1",76,0);')
        # mel.eval('setCharacterObject("thumb_04_r_Jx", "Character1",77,0);')
        # mel.eval('setCharacterObject("index_01_r", "Character1",78,0);')
        # mel.eval('setCharacterObject("index_02_r", "Character1",79,0);')
        # mel.eval('setCharacterObject("index_03_r", "Character1",80,0);')
        # mel.eval('setCharacterObject("index_04_r_Jx", "Character1",81,0);')
        # mel.eval('setCharacterObject("middle_01_r", "Character1",82,0);')
        # mel.eval('setCharacterObject("middle_02_r", "Character1",83,0);')
        # mel.eval('setCharacterObject("middle_03_r", "Character1",84,0);')
        # mel.eval('setCharacterObject("middle_04_r_Jx", "Character1",85,0);')
        # mel.eval('setCharacterObject("ring_01_r", "Character1",86,0);')
        # mel.eval('setCharacterObject("ring_02_r", "Character1",87,0);')
        # mel.eval('setCharacterObject("ring_03_r", "Character1",88,0);')
        # mel.eval('setCharacterObject("ring_04_r_Jx", "Character1",89,0);')
        # mel.eval('setCharacterObject("pinky_01_r", "Character1",90,0);')
        # mel.eval('setCharacterObject("pinky_02_r", "Character1",91,0);')
        # mel.eval('setCharacterObject("pinky_03_r", "Character1",92,0);')
        # mel.eval('setCharacterObject("pinky_04_r_Jx", "Character1",93,0);')
        # #94-97 is 6th right hand finger
        # #98-101 is 6th left foot toe
        # #102-121 are left foot toes
        # #122-125 is 6th right foot toe
        # #126-145 are right foot toes
        # #146 is left hand thumb 0

        # mel.eval('hikUpdateDefinitionUI;')
        # mel.eval('LockSkeletonDefinition();')

        # mel.eval('hikCreateControlRig;')
        # cmds.parent('Character1_Ctrl_Reference', 'Character1_Root_CNT')

    elif mode == 'connect':
        if not src.has_attr('Character'):
            _trg_plug = char.plug[trg]
            if src.object_type() not in ('transform', 'joint'):
                raise RuntimeError(src, src.object_type())
            src.add_attr('Character', _trg_plug)
        else:
            src.plug['Character'].connect(char.plug[trg], force=True)
    else:
        raise NotImplementedError(mode)


def _find_map_src(trg, mapping):
    """Find the source joint for the given target in this mapping.

    Args:
        trg (str): hik target
        mapping (dict): hik mapping

    Returns:
        (CJoint): source joint
    """
    _result = single([_src for _src, _trg in mapping if _trg == trg])
    return _result


def _skel_to_mapping(skel):  # pylint: disable=too-many-branches
    """Obtain joint mapping for the given skeleton.

    Args:
        skel (CSkeleton): skeleton to map

    Returns:
        (dict): skeleton HIK joint mapping
    """

    # Build name map
    _name = skel.to_name(catch=True)

    # Use default 1:1 name map
    if _name in ('Mutant', 'Carl', 'Adam', 'Mia', 'Swat', None):
        _jnts = ['Hips', 'Spine', 'Spine1', 'Spine2', 'Spine3', 'Neck', 'Head']
        for _side in ['Left', 'Right']:
            for _name in [
                    'UpLeg', 'Leg', 'Foot', 'ToeBase', 'Shoulder', 'Arm',
                    'ForeArm', 'Hand']:
                _jnt = f'{_side}{_name}'
                _jnts.append(_jnt)
            for _finger in ['Index', 'Middle', 'Pinky', 'Ring', 'Thumb']:
                for _idx in range(1, 5):
                    _jnt = f'{_side}Hand{_finger}{_idx}'
                    _jnts.append(_jnt)
        # pprint.pprint(_jnts)
        assert len(_jnts) == len(set(_jnts))
        _jnt_map = []
        _names = {_jnt.to_clean() for _jnt in skel.joints}
        for _jnt in _jnts:
            if _jnt not in _names:
                continue
            _jnt_map.append((_jnt, _jnt))

    elif skel.name == 'CMU':
        _jnt_map = [
            ('root', 'Hips'),
            ('upperback', 'Spine'),
            ('thorax', 'Spine1'),
            ('lowerneck', 'Neck'),
            ('upperneck', 'Neck1'),
            ('head', 'Head')]
        for _side_skel, _side_hik in [
                ('l', 'Left'),
                ('r', 'Right')]:
            for _src, _dest in [
                    ('femur', 'UpLeg'),
                    ('tibia', 'Leg'),
                    ('foot', 'Foot'),
                    ('toes', 'ToeBase'),
                    ('humerus', 'Arm'),
                    ('radius', 'ForeArm'),
                    ('hand', 'Hand')]:
                _jnt_map.append((_side_skel + _src, _side_hik + _dest))

    else:
        raise ValueError(skel.name)

    # Setup mapping
    _mapping = []
    _grp = skel.root.to_parent()
    if _grp:
        _mapping.append((_grp, 'Reference'))
    for _src, _trg in _jnt_map:
        _mapping.append((skel.to_joint(_src, catch=False), _trg))

    return _mapping


@restore_ns
def build_hik(mapping, name='Auto', straighten_arms=False):
    """Build an HIK character for the given skeleton.

    NOTE: the ui doesn't seem to update after building the HIK, but aside
    from that everything else seems to work.

    Args:
        mapping (dict): joint/target mapping
        name (str): HIK character name
        straighten_arms (bool): apply arm align with y axis to allow locking
            of character definition

    Returns:
        (HIKCharacter): new character
    """
    _LOGGER.info('BUILD HIK CHARACTER %s', name)

    _mapping = mapping
    if isinstance(_mapping, pom.CSkeleton):
        _mapping = _skel_to_mapping(_mapping)
    assert isinstance(_mapping, list)
    _root = _find_map_src('Hips', _mapping)
    _skel = pom.CSkeleton(_root)

    # Create character defintion
    assert not pom.find_nodes(type_='HIKCharacterNode', namespace=None)
    cmds.HIKCharacterControlsTool()
    set_namespace(':')
    try:
        mel.eval('hikCreateDefinition()')
    except SystemError:
        pass
    assert pom.find_nodes(type_='HIKCharacterNode', namespace=None)
    _hikc = single(pom.find_nodes(type_='HIKCharacterNode', namespace=None))

    for _jnt, _hik in _mapping:
        _LOGGER.debug(' - BIND HIK %s -> %s', _jnt, _hik)
        _assign_hik_jnt(src=_jnt, trg=_hik, char=_hikc)

    # Straighten arms (for locking)
    if straighten_arms:
        for _jnt in [
                _find_map_src('LeftArm', _mapping),
                _find_map_src('LeftForeArm', _mapping),
                _find_map_src('RightArm', _mapping),
                _find_map_src('RightForeArm', _mapping),
        ]:
            _jnt = pom.CJoint(_jnt)
            _lx = _jnt.to_m().to_lx().normalized()
            _x_plane = pom.CVector(_lx.x, 0, _lx.z)
            _rz = _x_plane.angle_to(_lx)
            _jnt.rz.set_val(_rz)

    set_current(_hikc)
    mel.eval('hikToggleLockDefinition()')

    # Reset after straighten
    if straighten_arms:
        _skel.zero()

    _name = cmds.rename(_hikc, name)
    return find_hik(_name)


def find_hik(match=None, catch=False, **kwargs):
    """Find an HIK node in this scene.

    Args:
        match (str): match by name/namespace
        catch (bool): no error if no HIK matching node found

    Returns:
        (PHIKNode): HIK
    """
    _LOGGER.debug('FIND HIK %s %s', match, kwargs)
    _hiks = find_hiks(**kwargs)
    _LOGGER.debug(' - FOUND %d HIKS %s', len(_hiks), _hiks)
    if len(_hiks) == 1:
        return single(_hiks)

    if isinstance(match, (pom.CReference, pom.CNode, pipe_ref.CPipeRef)):
        _ns_hiks = [
            _hik for _hik in _hiks if _hik.namespace == match.namespace]
        _LOGGER.debug(' - FOUND %d NS HIKS %s', len(_ns_hiks), _ns_hiks)
        if len(_ns_hiks) == 1:
            return single(_ns_hiks)

    if isinstance(match, str):

        # Try exact string match
        _str_hiks = [
            _hik for _hik in _hiks if match in (
                str(_hik), _hik.namespace, f':{_hik.namespace}')]
        _LOGGER.debug(' - FOUND %d STR HIKS %s', len(_str_hiks), _str_hiks)
        if len(_str_hiks) == 1:
            return single(_str_hiks)

        # Try filter match
        _filter_hiks = [
            _hik for _hik in _hiks if passes_filter(str(_hik), match)]
        if len(_filter_hiks) == 1:
            return single(_filter_hiks)

    if catch:
        return False
    raise ValueError(match, kwargs)


def find_hiks(referenced=None, task=None, namespace=EMPTY):
    """Find HIK nodes in this scene.

    Args:
        referenced (bool): filter by referenced status
        task (str): filter by task
        namespace (str): apply namespace filter

    Returns:
        (PHIKNode list): HIKs
    """
    refresh_ui()
    _hiks = []
    for _item in CHAR_LIST.get_vals():

        if _item == 'None':
            continue

        _hik = PHIKNode(_item)
        if referenced is not None and _hik.is_referenced() != referenced:
            continue

        # Apply task filter
        _out = None
        _ref = pom.find_ref(namespace=_hik.namespace)
        if _ref:
            _out = pipe.to_output(_ref.path, catch=True)
        if task and (not _out or not _out.task == task):
            continue

        # Apply namespace filter
        if namespace is EMPTY:
            pass
        elif namespace is None:
            if _hik.namespace:
                continue
        elif namespace != _hik.namespace:
            continue

        _hiks.append(_hik)

    return _hiks


def get_source(hik):
    """Get source of the given HIK.

    Args:
        hik (str): HIK node to read

    Returns:
       (None|str|PHIKNode): source (HIK, control rig or None)
    """
    _hik = find_hik(hik)
    return _hik.get_source()


def _read_step_size(keys, force):
    """Read step size from the given list of key frames.

    Args:
        keys (float list): frames of keys
        force (bool): supress any warnings

    Returns:
        (float): step size
    """

    # Read steps between all keys
    _steps = collections.defaultdict(int)
    _keys = sorted(set(keys))
    for _idx in range(len(_keys) - 1):
        _step = round(_keys[_idx + 1] - _keys[_idx], 4)
        _steps[_step] += 1
    _steps = dict(_steps)
    _LOGGER.info(' - STEPS %s', _steps)

    _step = single(_steps.keys(), catch=True)
    if _step:
        return _step

    # Use most common step if not clear
    for _step, _count in list(_steps.items()):
        if _count <= 3:
            del _steps[_step]
    _step = single(_steps.keys(), catch=True)
    if _step:
        return _step

    pprint.pprint(_steps)
    _size = sorted((_count, _size) for _size, _count in _steps.items())[-1][1]
    if not force:
        qt.ok_cancel(
            'Failed to accurately determine anim step size.\n\n'
            f'Using most common step size {_size:.04f} frames.')
    return _size


def refresh_ui(show=False):
    """Refresh HIK interface.

    Args:
        show (bool): show the interface (can trigger update)
    """
    if show or not CHAR_LIST.exists():
        show_ui()
    mel.eval('hikUpdateCharacterList()')
    process_deferred_events()
    mel.eval('hikUpdateSourceList()')
    process_deferred_events()
    cmds.refresh()
    process_deferred_events()


def show_ui():
    """Show HIK interface."""
    mel.eval('HIKCharacterControlsTool')
    cmds.refresh()


def set_current(hik):
    """Set current character in maya's HIK ui.

    Args:
        hik (str): node/namespace to match
    """
    if hik is None:
        CHAR_LIST.set_val('None')
        return
    _hik = find_hik(hik)
    _hik.set_current()


def set_source(hik, source):
    """Set source for the given HIK system.

    Args:
        hik (str): HIK node to update
        source (str): name of source to apply
    """
    _hik = find_hik(hik)
    _hik.set_source(source)
