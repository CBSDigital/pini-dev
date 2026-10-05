"""Tools for managing human IK."""

# pylint: disable=too-many-lines

import collections
import logging
import pprint

from pini import pipe, qt, icons
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

    def bake_to_skel(  # pylint: disable=too-many-branches,too-many-statements
            self, range_=None, step=None, loop=False, skel=None,
            euler_filter=True, simulation=True, plugs=None,
            add_anim_offs=False, force=False):
        """Bake animation to skeleton.

        Args:
            range_ (tuple): override range (otherwise read from anim)
            step (float): override step size (otherwise read from anim)
            loop (bool): apply looping
            skel (CSkeleton): skeleton to bake to
            euler_filter (bool): apply euler filter
            simulation (bool): bake as simulation (moves timelines - best to
                have on to see progress)
            plugs (CPlug list): override list of plugs to bake
            add_anim_offs (bool): add anim offset controls
            force (bool): supress any bake warnings
        """
        _LOGGER.info('BAKE TO SKEL %s', self)
        _skel = skel or self.to_skel()
        _LOGGER.info(' - SKEL %s', _skel)

        # Read range + step size from source anim
        _hips = self.read_map()['Hips']
        _rng = range_
        _step = step
        if not _rng or not step:
            _src = self.get_source()
            if not _src:
                raise RuntimeError(f'Failed to determine HIK source {self}')
            _LOGGER.info(' - HIPS %s', _hips)
            _src_ktvs = _src.read_map()['Hips'].rx.get_ktvs()
            assert _src_ktvs
            _src_keys = [_time for _time, _ in _src_ktvs]
            _LOGGER.info(' - SRC KEYS %s', _src_keys)
            if not _step:
                _step = _read_step_size(_src_keys, force=force)
            if not _rng:
                _rng = _src_keys[0], _src_keys[-1]
        _LOGGER.info(' - RANGE / STEP %s %s', _rng, _step)

        # Get list of plugs to bake
        _plugs = plugs or self.to_plugs()

        # Bake anim (copied from HIK bake to skeleton)
        _LOGGER.info(' - PLUGS %s', _plugs)
        mel.eval(f'hikBakeCharacterPre "{self}"')
        cmds.bakeResults(
            _plugs, simulation=simulation, time=_rng, sampleBy=_step,
            oversamplingRate=1, disableImplicitControl=True,
            preserveOutsideKeys=True, sparseAnimCurveBake=False,
            removeBakedAttributeFromLayer=False,
            removeBakedAnimFromLayer=False, bakeOnOverrideLayer=False,
            minimizeRotation=True, controlPoints=False, shape=True)
        mel.eval(f'hikBakeCharacterPost "{self}"')
        cmds.DeleteAllStaticChannels()
        if euler_filter:
            cmds.filterCurve(_plugs)

        # Apply looping
        _anims = list(filter(bool, [_plug.to_anim() for _plug in _plugs]))
        _LOGGER.info(' - BUILD %d ANIMS %s', len(_anims), _anims)
        if loop:
            _LOGGER.debug(' - APPLY LOOP %s', loop)
            if loop == 'Path':
                _offs_trgs = [_hips.tz]
            elif loop in (True, 'Loopable'):
                _offs_trgs = []
            else:
                raise ValueError(loop)
            for _crv in _anims:
                _LOGGER.debug(' - CURVE %s', _crv)
                if not _crv.output.find_connections():
                    _LOGGER.debug('   - DELETE UNCONNECTED')
                    _crv.delete()
                    continue
                _offs = _crv.target in _offs_trgs
                _LOGGER.debug('   - OFFS %s', _offs)
                _crv.loop(offset=_offs)

        # Apply spline tangents
        for _anim in _anims:
            _anim.set_tangents('spline')

        if add_anim_offs:
            _rig = pom.find_ref(namespace=self.namespace)
            pom.add_anim_offs(anims=_anims, tfm=_rig.top_node)

    def is_locked(self):
        """Test whether this character definition is locked.

        Returns:
            (bool): whether locked
        """
        return self.plug['InputCharacterizationLock'].get_val()

    def lock(self):
        """Lock this character definition."""
        if self.is_locked():
            _LOGGER.info('ALREADY LOCKED %s', self)
            return
        self.set_current()
        mel.eval('hikToggleLockDefinition')
        process_deferred_events()

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

        process_deferred_events()

        assert CHAR_LIST.get_val() == self

    def read_map(self, result='node'):
        """Read current HIK mapping.

        Args:
            result (str): type of result to return
                node - hik joint name / joint node dict
                clean - hik joint name / clean joint name dict
                hik - hik joint name / clean joint name tuple list (for code)

        Returns:
            (dict): bone name / joint mappings
        """
        _LOGGER.debug('READ MAP %s', self)
        _map = {}
        for _src, _dest in self.find_connections(type_='joint'):
            _LOGGER.debug(' - SRC / DEST "%s" -> "%s"', _src, _dest)

            # Read connection to attr
            if _src.to_node() == self:
                assert _dest.attr == 'Character'
                _val = _dest.to_node()
                _key = _src.attr
            elif _dest.to_node() == self:
                assert _src.attr == 'Character'
                _key = _dest.attr
                _val = _src.to_node()
            else:
                raise ValueError

            # Apply result mode
            if result == 'node':
                pass
            elif result in ('clean', 'hik'):
                _val = _val.to_clean()
            else:
                raise ValueError(result)

            _map[_key] = _val

        if result == 'hik':
            return [(_val, _key) for _key, _val in _map.items()]

        return _map

    def to_hips(self):
        """Obtain hip joint for this skeleton.

        Returns:
            (CJoint): hips
        """
        return self.read_map()['Hips']

    def to_jnts(self):
        """Read HIK joints from character definition.

        Returns:
            (CTransform list): joints
        """
        _jnts = set()
        for _src, _dest in self.find_incoming():
            if _src.attr != 'Character':
                continue
            _jnts.add(_src.node)
        _jnts = sorted(_jnts)
        return _jnts

    def to_plugs(self):
        """Read plugs controlled by HIK from character definition.

        Returns:
            (CPlug list): plugs
        """
        return sum([
            _jnt.to_tfm_plugs(scale=False) for _jnt in self.to_jnts()],
            [])

    def to_skel(self):
        """Obtain this HIK system's skeleton.

        Returns:
            (CSkeleton): skeleton
        """
        _hips = self.plug['Hips']
        _root = _hips.find_incoming(plugs=False)
        if not _root:
            _root = single(_hips.find_outgoing(plugs=False))
        return pom.CSkeleton(_root)


def _assign_hik_jnt(src, trg, char):
    """Assign a joint to the an HIK character joint.

    Args:
        src (CJoint): joint to assign
        trg (str): name of HIK joint to connect to
        char (PHIKNode): HIK character to update
    """
    _LOGGER.debug('BIND HIK JNT %s -> %s (%s)', src, trg, char)
    if not src.has_attr('Character'):
        _trg_plug = char.plug[trg]
        if src.object_type() not in ('transform', 'joint'):
            raise RuntimeError(src, src.object_type())
        src.add_attr('Character', _trg_plug)
    src.plug['Character'].connect(char.plug[trg], force=True)


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
    qt.ok_cancel(
        f'No mapping found for skeleton "{skel.name}".\n\n'
        'Building mapping from code - this should only happen once.',
        icon=icons.find('Skull'))

    # Build name map
    _name = skel.to_name(catch=True)

    # Use default 1:1 name map
    if _name in (
            'Mutant', 'Carl', 'Adam', 'Mia', 'Swat', None, 'RokokoRaw1',
            'Hou'):
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

    elif skel.name in ('RokokoRaw2', 'Rokoko1'):
        _jnt_map = [
            ('Root', 'Reference'),
            ('Hips', 'Hips'),
            ('Spine1', 'Spine'),
            ('Spine2', 'Spine1'),
            ('Spine3', 'Spine2'),
            ('Spine4', 'Spine3'),
            ('Neck', 'Head'),
            ('RightArm', 'RightArm'),
            ('LeftArm', 'LeftArm'),
            ('RightForeArm', 'RightForeArm'),
            ('LeftForeArm', 'LeftForeArm'),
            ('RightHand', 'RightHand'),
            ('LeftHand', 'LeftHand'),
            ('RightFinger1Metacarpal', 'RightHandThumb1'),
            ('LeftFinger1Metacarpal', 'LeftHandThumb1'),
            ('LeftFinger1Proximal', 'LeftHandThumb2'),
            ('RightFinger1Proximal', 'RightHandThumb2'),
            ('RightFinger1Distal', 'RightHandThumb3'),
            ('LeftFinger1Distal', 'LeftHandThumb3'),
            ('LeftFinger2Metacarpal', 'LeftHandIndex1'),
            ('RightFinger2Metacarpal', 'RightHandIndex1'),
            ('RightFinger2Proximal', 'RightHandIndex2'),
            ('LeftFinger2Proximal', 'LeftHandIndex2'),
            ('LeftFinger2Medial', 'LeftHandIndex3'),
            ('RightFinger2Medial', 'RightHandIndex3'),
            ('LeftFinger3Metacarpal', 'LeftHandMiddle1'),
            ('RightFinger3Metacarpal', 'RightHandMiddle1'),
            ('RightFinger3Proximal', 'RightHandMiddle2'),
            ('LeftFinger3Proximal', 'LeftHandMiddle2'),
            ('LeftFinger3Medial', 'LeftHandMiddle3'),
            ('RightFinger3Medial', 'RightHandMiddle3'),
            ('RightFinger4Metacarpal', 'RightHandRing1'),
            ('LeftFinger4Metacarpal', 'LeftHandRing1'),
            ('RightFinger4Proximal', 'LeftHandRing2'),
            ('LeftFinger4Proximal', 'RightHandRing2'),
            ('LeftFinger4Distal', 'RightHandRing3'),
            ('RightFinger4Distal', 'LeftHandRing3'),
            ('LeftFinger5Metacarpal', 'LeftHandPinky1'),
            ('RightFinger5Metacarpal', 'RightHandPinky1'),
            ('RightFinger5Proximal', 'RightHandPinky2'),
            ('LeftFinger5Proximal', 'LeftHandPinky2'),
            ('LeftFinger5Medial', 'LeftHandPinky3'),
            ('RightFinger5Medial', 'RightHandPinky3'),
            ('RightThigh', 'RightUpLeg'),
            ('LeftThigh', 'LeftUpLeg'),
            ('RightShin', 'RightLeg'),
            ('LeftShin', 'LeftLeg'),
            ('RightFoot', 'RightFoot'),
            ('LeftFoot', 'LeftFoot')]
        if skel.name == 'Rokoko1':
            _jnt_map.pop(0)

    elif skel.name in ('HouSkel1', ):
        _jnt_map = [
            ('Root', 'Hips'),
            ('Spine1', 'Spine'),
            ('Spine2', 'Spine1'),
            ('Spine3', 'Spine2'),
            ('Spine4', 'Spine3'),
            ('Chest', 'Spine4'),
            ('Head', 'Head'),
            ('Neck', 'Neck'),
            ('RightShoulder', 'RightShoulder'),
            ('LeftShoulder', 'LeftShoulder'),
            ('RightUpperArm', 'RightArm'),
            ('LeftUpperArm', 'LeftArm'),
            ('RightElbow', 'RightForeArm'),
            ('LeftElbow', 'LeftForeArm'),
            ('RightHand', 'RightHand'),
            ('LeftHand', 'LeftHand'),
            ('RightThumb1', 'RightHandThumb1'),
            ('LeftThumb1', 'LeftHandThumb1'),
            ('LeftThumb2', 'LeftHandThumb2'),
            ('RightThumb2', 'RightHandThumb2'),
            ('RightThumb3', 'RightHandThumb3'),
            ('LeftThumb3', 'LeftHandThumb3'),
            ('LeftThumb4', 'LeftHandThumb4'),
            ('RightThumb4', 'RightHandThumb4'),
            ('RightIndex2', 'RightHandIndex1'),
            ('LeftIndex2', 'LeftHandIndex1'),
            ('RightIndex3', 'RightHandIndex2'),
            ('LeftIndex3', 'LeftHandIndex2'),
            ('RightIndex1', 'RightInHandIndex'),
            ('LeftIndex1', 'LeftInHandIndex'),
            ('RightIndex4', 'RightHandIndex3'),
            ('LeftIndex4', 'LeftHandIndex3'),
            ('RightIndex5', 'RightHandIndex4'),
            ('LeftIndex5', 'LeftHandIndex4'),
            ('RightMiddle1', 'RightInHandMiddle'),
            ('LeftMiddle1', 'LeftInHandMiddle'),
            ('RightMiddle2', 'RightHandMiddle1'),
            ('LeftMiddle2', 'LeftHandMiddle1'),
            ('RightMiddle3', 'RightHandMiddle2'),
            ('LeftMiddle3', 'LeftHandMiddle2'),
            ('RightMiddle4', 'RightHandMiddle3'),
            ('LeftMiddle4', 'LeftHandMiddle3'),
            ('RightMiddle5', 'RightHandMiddle4'),
            ('LeftMiddle5', 'LeftHandMiddle4'),
            ('RightRing1', 'RightInHandRing'),
            ('LeftRing1', 'LeftInHandRing'),
            ('RightRing2', 'RightHandRing1'),
            ('LeftRing2', 'LeftHandRing1'),
            ('RightRing3', 'RightHandRing2'),
            ('LeftRing3', 'LeftHandRing2'),
            ('RightRing4', 'RightHandRing3'),
            ('LeftRing4', 'LeftHandRing3'),
            ('RightRing5', 'RightHandRing4'),
            ('LeftRing5', 'LeftHandRing4'),
            ('RightPinky1', 'RightInHandPinky'),
            ('LeftPinky1', 'LeftInHandPinky'),
            ('RightPinky2', 'RightHandPinky1'),
            ('LeftPinky2', 'LeftHandPinky1'),
            ('RightPinky3', 'RightHandPinky2'),
            ('LeftPinky3', 'LeftHandPinky2'),
            ('RightPinky4', 'RightHandPinky3'),
            ('LeftPinky4', 'LeftHandPinky3'),
            ('RightPinky5', 'RightHandPinky4'),
            ('LeftPinky5', 'LeftHandPinky4'),
            ('RightHip', 'RightUpLeg'),
            ('RightKnee', 'RightLeg'),
            ('LeftKnee', 'LeftLeg'),
            ('RightHeel', 'RightFoot'),
            ('LeftHeel', 'LeftFoot'),
            ('RightBall', 'RightToeBase'),
            ('LeftBall', 'LeftToeBase'),
            # ('RightToe', 'LeftFootExtraFinger1'),
            # ('LeftToe', 'RightFootExtraFinger1'),
            ('LeftHip', 'LeftUpLeg')]

    elif skel.name == 'Mimem':

        _jnt_map = [
            ('reference', 'Reference'),
            ('hips', 'Hips'),
            ('spine_01', 'Spine'),
            ('spine_02', 'Spine1'),
            ('spine_03', 'Spine2'),
            ('arm_stretch_r', 'RightArm'),
            ('arm_stretch_l', 'LeftArm'),
            ('forearm_stretch_l', 'LeftForeArm'),
            ('forearm_stretch_r', 'RightForeArm'),
            ('hand_r', 'RightHand'),
            ('hand_l', 'LeftHand'),
            ('c_thumb1_r', 'RightHandThumb1'),
            ('c_thumb1_l', 'LeftHandThumb1'),
            ('c_thumb2_l', 'LeftHandThumb2'),
            ('c_thumb2_r', 'RightHandThumb2'),
            ('c_thumb3_r', 'RightHandThumb3'),
            ('c_thumb3_l', 'LeftHandThumb3'),
            ('c_index1_l', 'LeftHandIndex1'),
            ('c_index1_r', 'RightHandIndex1'),
            ('c_index2_r', 'RightHandIndex2'),
            ('c_index2_l', 'LeftHandIndex2'),
            ('c_index3_l', 'LeftHandIndex3'),
            ('c_index3_r', 'RightHandIndex3'),
            ('c_middle1_r', 'RightHandMiddle1'),
            ('c_middle1_l', 'LeftHandMiddle1'),
            ('c_middle2_l', 'LeftHandMiddle2'),
            ('c_middle2_r', 'RightHandMiddle2'),
            ('c_middle3_r', 'RightHandMiddle3'),
            ('c_middle3_l', 'LeftHandMiddle3'),
            ('c_ring1_l', 'LeftHandRing1'),
            ('c_ring1_r', 'RightHandRing1'),
            ('c_ring2_r', 'RightHandRing2'),
            ('c_ring3_r', 'RightHandRing3'),
            ('c_pinky1_r', 'RightHandPinky1'),
            ('c_pinky1_l', 'LeftHandPinky1'),
            ('c_pinky2_l', 'LeftHandPinky2'),
            ('c_pinky2_r', 'RightHandPinky2'),
            ('c_pinky3_l', 'LeftHandPinky3'),
            ('c_pinky3_r', 'RightHandPinky3'),
            ('thigh_stretch_r', 'RightUpLeg'),
            ('thigh_stretch_l', 'LeftUpLeg'),
            ('leg_stretch_r', 'RightLeg'),
            ('leg_stretch_l', 'LeftLeg'),
            ('foot_r', 'RightFoot'),
            ('foot_l', 'LeftFoot'),
            ('toes_01_r', 'RightToeBase'),
            ('toes_01_l', 'LeftToeBase'),
            ('head', 'Head'),
            ('neck', 'Neck'),
            ('shoulder_r', 'RightShoulder'),
            ('shoulder_l', 'LeftShoulder')]

    elif skel.name in ('Unreal', 'HouUnreal'):

        _jnt_map = [
            ('root', 'Reference'),
            ('pelvis', 'Hips'),
            ('spine_01', 'Spine'),
            ('spine_02', 'Spine1'),
            ('spine_03', 'Spine2'),
            ('spine_04', 'Spine3'),
            ('spine_05', 'Spine4'),
            ('neck_01', 'Neck'),
            ('neck_02', 'Neck1'),
            ('head', 'Head'),
            ('upperarm_l', 'LeftArm'),
            ('lowerarm_l', 'LeftForeArm'),
            ('hand_l', 'LeftHand'),
            ('pinky_metacarpal_l', 'LeftInHandPinky'),
            ('pinky_01_l', 'LeftHandPinky1'),
            ('pinky_02_l', 'LeftHandPinky2'),
            ('pinky_03_l', 'LeftHandPinky3'),
            ('ring_metacarpal_l', 'LeftInHandRing'),
            ('ring_01_l', 'LeftHandRing1'),
            ('ring_02_l', 'LeftHandRing2'),
            ('ring_03_l', 'LeftHandRing3'),
            ('thumb_01_l', 'LeftHandThumb1'),
            ('thumb_02_l', 'LeftHandThumb2'),
            ('thumb_03_l', 'LeftHandThumb3'),
            ('middle_metacarpal_l', 'LeftInHandMiddle'),
            ('middle_01_l', 'LeftHandMiddle1'),
            ('middle_02_l', 'LeftHandMiddle2'),
            ('middle_03_l', 'LeftHandMiddle3'),
            ('index_metacarpal_l', 'LeftInHandIndex'),
            ('index_01_l', 'LeftHandIndex1'),
            ('index_02_l', 'LeftHandIndex2'),
            ('index_03_l', 'LeftHandIndex3'),
            ('upperarm_r', 'RightArm'),
            ('lowerarm_r', 'RightForeArm'),
            ('hand_r', 'RightHand'),
            ('pinky_metacarpal_r', 'RightInHandPinky'),
            ('pinky_01_r', 'RightHandPinky1'),
            ('pinky_02_r', 'RightHandPinky2'),
            ('pinky_03_r', 'RightHandPinky3'),
            ('ring_metacarpal_r', 'RightInHandRing'),
            ('ring_01_r', 'RightHandRing1'),
            ('ring_02_r', 'RightHandRing2'),
            ('ring_03_r', 'RightHandRing3'),
            ('thumb_01_r', 'RightHandThumb1'),
            ('thumb_02_r', 'RightHandThumb2'),
            ('thumb_03_r', 'RightHandThumb3'),
            ('middle_metacarpal_r', 'RightInHandMiddle'),
            ('middle_01_r', 'RightHandMiddle1'),
            ('middle_02_r', 'RightHandMiddle2'),
            ('middle_03_r', 'RightHandMiddle3'),
            ('index_metacarpal_r', 'RightInHandIndex'),
            ('index_01_r', 'RightHandIndex1'),
            ('index_02_r', 'RightHandIndex2'),
            ('index_03_r', 'RightHandIndex3'),
            ('thigh_r', 'RightUpLeg'),
            ('calf_r', 'RightLeg'),
            ('foot_r', 'RightFoot'),
            ('ball_r', 'RightToeBase'),
            ('littletoe_01_r', 'RightFootPinky1'),
            ('littletoe_02_r', 'RightFootPinky2'),
            ('ringtoe_01_r', 'RightFootRing1'),
            ('ringtoe_02_r', 'RightFootRing2'),
            ('middletoe_01_r', 'RightFootMiddle1'),
            ('middletoe_02_r', 'RightFootMiddle2'),
            ('bigtoe_01_r', 'RightFootExtraFinger1'),
            ('bigtoe_02_r', 'RightFootExtraFinger2'),
            ('indextoe_01_r', 'RightFootIndex1'),
            ('indextoe_02_r', 'RightFootIndex2'),
            ('thigh_l', 'LeftUpLeg'),
            ('calf_l', 'LeftLeg'),
            ('foot_l', 'LeftFoot'),
            ('indextoe_01_l', 'LeftFootIndex1'),
            ('indextoe_02_l', 'LeftFootIndex2'),
            ('bigtoe_01_l', 'LeftFootExtraFinger1'),
            ('bigtoe_02_l', 'LeftFootExtraFinger2'),
            ('littletoe_01_l', 'LeftFootPinky1'),
            ('littletoe_02_l', 'LeftFootPinky2'),
            ('middletoe_01_l', 'LeftFootMiddle1'),
            ('middletoe_02_l', 'LeftFootMiddle2'),
            ('ringtoe_01_l', 'LeftFootRing1'),
            ('ringtoe_02_l', 'LeftFootRing2')]

    elif skel.name in ('HouUnreal2', 'HouUnreal3', 'HouUnreal4'):

        _jnt_map = [
            ('pelvis', 'Hips'),
            ('spine_01', 'Spine'),
            ('spine_02', 'Spine1'),
            ('spine_03', 'Spine2'),
            ('spine_04', 'Spine3'),
            ('spine_05', 'Spine4'),
            ('neck_01', 'Neck'),
            ('neck_02', 'Neck1'),
            ('head', 'Head'),
            ('upperarm_l', 'LeftArm'),
            ('lowerarm_l', 'LeftForeArm'),
            ('hand_l', 'LeftHand'),
            ('pinky_metacarpal_l', 'LeftInHandPinky'),
            ('pinky_01_l', 'LeftHandPinky1'),
            ('pinky_02_l', 'LeftHandPinky2'),
            ('pinky_03_l', 'LeftHandPinky3'),
            ('ring_metacarpal_l', 'LeftInHandRing'),
            ('ring_01_l', 'LeftHandRing1'),
            ('ring_02_l', 'LeftHandRing2'),
            ('ring_03_l', 'LeftHandRing3'),
            ('thumb_01_l', 'LeftHandThumb1'),
            ('thumb_02_l', 'LeftHandThumb2'),
            ('thumb_03_l', 'LeftHandThumb3'),
            ('middle_metacarpal_l', 'LeftInHandMiddle'),
            ('middle_01_l', 'LeftHandMiddle1'),
            ('middle_02_l', 'LeftHandMiddle2'),
            ('middle_03_l', 'LeftHandMiddle3'),
            ('index_metacarpal_l', 'LeftInHandIndex'),
            ('index_01_l', 'LeftHandIndex1'),
            ('index_02_l', 'LeftHandIndex2'),
            ('index_03_l', 'LeftHandIndex3'),
            ('upperarm_r', 'RightArm'),
            ('lowerarm_r', 'RightForeArm'),
            ('hand_r', 'RightHand'),
            ('pinky_metacarpal_r', 'RightInHandPinky'),
            ('pinky_01_r', 'RightHandPinky1'),
            ('pinky_02_r', 'RightHandPinky2'),
            ('pinky_03_r', 'RightHandPinky3'),
            ('ring_metacarpal_r', 'RightInHandRing'),
            ('ring_01_r', 'RightHandRing1'),
            ('ring_02_r', 'RightHandRing2'),
            ('ring_03_r', 'RightHandRing3'),
            ('thumb_01_r', 'RightHandThumb1'),
            ('thumb_02_r', 'RightHandThumb2'),
            ('thumb_03_r', 'RightHandThumb3'),
            ('middle_metacarpal_r', 'RightInHandMiddle'),
            ('middle_01_r', 'RightHandMiddle1'),
            ('middle_02_r', 'RightHandMiddle2'),
            ('middle_03_r', 'RightHandMiddle3'),
            ('index_metacarpal_r', 'RightInHandIndex'),
            ('index_01_r', 'RightHandIndex1'),
            ('index_02_r', 'RightHandIndex2'),
            ('index_03_r', 'RightHandIndex3'),
            ('thigh_r', 'RightUpLeg'),
            ('calf_r', 'RightLeg'),
            ('foot_r', 'RightFoot'),
            ('ball_r', 'RightToeBase'),
            ('littletoe_01_r', 'RightFootPinky1'),
            ('littletoe_02_r', 'RightFootPinky2'),
            ('ringtoe_01_r', 'RightFootRing1'),
            ('ringtoe_02_r', 'RightFootRing2'),
            ('middletoe_01_r', 'RightFootMiddle1'),
            ('middletoe_02_r', 'RightFootMiddle2'),
            ('bigtoe_01_r', 'RightFootExtraFinger1'),
            ('bigtoe_02_r', 'RightFootExtraFinger2'),
            ('indextoe_01_r', 'RightFootIndex1'),
            ('indextoe_02_r', 'RightFootIndex2'),
            ('thigh_l', 'LeftUpLeg'),
            ('calf_l', 'LeftLeg'),
            ('foot_l', 'LeftFoot'),
            ('indextoe_01_l', 'LeftFootIndex1'),
            ('indextoe_02_l', 'LeftFootIndex2'),
            ('bigtoe_01_l', 'LeftFootExtraFinger1'),
            ('bigtoe_02_l', 'LeftFootExtraFinger2'),
            ('littletoe_01_l', 'LeftFootPinky1'),
            ('littletoe_02_l', 'LeftFootPinky2'),
            ('middletoe_01_l', 'LeftFootMiddle1'),
            ('middletoe_02_l', 'LeftFootMiddle2'),
            ('ringtoe_01_l', 'LeftFootRing1'),
            ('ringtoe_02_l', 'LeftFootRing2')]

    else:
        raise ValueError(skel.name)

    # Save to skel
    _dict = {_hik_name: _jnt_name for _jnt_name, _hik_name in _jnt_map}
    skel.set_hik_map(_dict)

    # Setup mapping
    _mapping = []
    _grp = skel.root.to_parent()
    if _grp:
        _mapping.append((_grp, 'Reference'))
    for _src, _trg in _jnt_map:
        _mapping.append((skel.to_joint(_src, catch=False), _trg))

    return _mapping


@restore_ns
def build_hik(
        target, name='Auto', straighten_arms=False, reset_ns=True,
        force=False):
    """Build an HIK character for the given skeleton.

    NOTE: the ui doesn't seem to update after building the HIK, but aside
    from that everything else seems to work.

    Args:
        target (dict|CSkeleton): joint/target mapping or skeleton
        name (str): HIK character name
        straighten_arms (bool): apply arm align with y axis to allow locking
            of character definition
        reset_ns (bool): build in root namespace (default: on)
        force (bool): replace any existing HIK system with the same name
            without confirmation

    Returns:
        (HIKCharacter): new character
    """
    _LOGGER.info('BUILD HIK CHARACTER %s', name)

    if cmds.objExists(name):
        if not force:
            raise RuntimeError(f'Node "{name}" already exists')
        cmds.delete(name)

    # Obtain mapping from target
    if isinstance(target, pom.CSkeleton):
        _skel_map = target.hik_map
        if _skel_map:
            _mapping = [
                (target.to_joint(_trg), _src)
                for _src, _trg in _skel_map.items()]
        else:
            _mapping = _skel_to_mapping(target)
    else:
        _mapping = target
    assert isinstance(_mapping, list)
    _LOGGER.debug(' - MAPPPING %s', _mapping)
    _root = _find_map_src('Hips', _mapping)
    _skel = pom.CSkeleton(_root)

    # Create character defintion
    _pre_hiks = pom.find_nodes(type_='HIKCharacterNode')
    cmds.HIKCharacterControlsTool()
    if reset_ns:
        set_namespace(':')
    try:
        mel.eval('hikCreateDefinition()')
    except SystemError:
        pass
    _post_hiks = pom.find_nodes(type_='HIKCharacterNode')
    _hikc = single(set(_post_hiks) - set(_pre_hiks))

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

        # Try to match name
        _name_hiks = [
            _hik for _hik in _hiks if _hik == match]
        _LOGGER.debug(' - FOUND %d NAME HIKS %s', len(_name_hiks), _name_hiks)
        if len(_name_hiks) == 1:
            return single(_name_hiks)

        # Try to match namespace
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
    _LOGGER.warning(' - FAILED TO FIND HIK %s', _hiks)
    _LOGGER.warning(' - MATCH / KWARGS %s %s', match, kwargs)
    raise ValueError(f'Failed to find hik {match or kwargs}')


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
