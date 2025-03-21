"""Tools for managing human IK."""

import logging

from pini.utils import single, passes_filter

from maya_pini import ui, open_maya as pom
from maya_pini.utils import process_deferred_events

from maya import cmds, mel

_LOGGER = logging.getLogger(__name__)

CHAR_LIST = ui.OptionMenuGrp('hikCharacterList')
SRC_LIST = ui.OptionMenuGrp('hikSourceList')

CONTROL_RIG = 'Control Rig'
STANCE = 'Stance'


class PHIKNode(pom.CNode):
    """Represent an HIKCharacter node."""

    def get_source(self):
        """Obtain source for this HIK node.

        Returns:
            (None|str|PHIKNode): source (HIK, control rig or None)
        """
        refresh_ui()
        CHAR_LIST.set_val(self)
        refresh_ui()
        _src = SRC_LIST.get_val().strip()
        _LOGGER.info('SOURCE %s = %s', self, _src)
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
        _LOGGER.debug(' - SELECTED "%s"', SRC_LIST.get_val())
        assert SRC_LIST.get_val() == f' {_select}'

    def set_current(self):
        """Set this HIK as current selection in the ui."""
        _LOGGER.debug(' - SET CURRENT %s', self)
        process_deferred_events()

        # Run HIK mel
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


def _assign_hik_jnt(src, trg, char):
    """Assign a joint to the an HIK character joint.

    Args:
        src (CJoint): joint to assign
        trg (str): name of HIK joint to connect to
        char (HIKCharacter): HIK character to update
    """
    _LOGGER.info('BIND HIK JNT %s -> %s (%s)', src, trg, char)
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
    _root = _find_map_src('Hips', mapping)
    _skel = pom.CSkeleton(_root)

    # Create character defintion
    assert not pom.find_nodes(type_='HIKCharacterNode', namespace=None)
    # mel.eval('hikCreateDefinition')
    cmds.HIKCharacterControlsTool()
    mel.eval('hikCreateDefinition()')
    assert pom.find_nodes(type_='HIKCharacterNode', namespace=None)
    _hikc = single(pom.find_nodes(type_='HIKCharacterNode', namespace=None))

    for _jnt, _hik in mapping:
        _LOGGER.debug(' - BIND HIK %s -> %s', _jnt, _hik)
        _assign_hik_jnt(src=_jnt, trg=_hik, char=_hikc)

    # Straighten arms (for locking)
    if straighten_arms:
        for _jnt in [
                _find_map_src('LeftArm', mapping),
                _find_map_src('LeftForeArm', mapping),
                _find_map_src('RightArm', mapping),
                _find_map_src('RightForeArm', mapping),
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


def find_hik(match=None, **kwargs):
    """Find an HIK node in this scene.

    Args:
        match (str): match by name/namespace

    Returns:
        (PHIKNode): HIK
    """
    _hiks = find_hiks(**kwargs)
    if len(_hiks) == 1:
        return single(_hiks)

    if isinstance(match, (pom.CReference, pom.CNode)):
        _ns_hiks = [
            _hik for _hik in _hiks if _hik.namespace == match.namespace]
        if len(_ns_hiks) == 1:
            return single(_ns_hiks)

    if isinstance(match, str):

        # Try exact string match
        _str_hiks = [
            _hik for _hik in _hiks if match in (str(_hik), _hik.namespace)]
        if len(_str_hiks) == 1:
            return single(_str_hiks)

        # Try filter match
        _filter_hiks = [
            _hik for _hik in _hiks if passes_filter(str(_hik), match)]
        if len(_filter_hiks) == 1:
            return single(_filter_hiks)

    raise ValueError(match, kwargs)


def find_hiks(referenced=None):
    """Find HIK nodes in this scene.

    Args:
        referenced (bool): filter by referenced status

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


def refresh_ui(show=False):
    """Refresh HIK interface.

    Args:
        show (bool): show the interface (can trigger update)
    """
    if show or not CHAR_LIST.exists():
        show_ui()
    mel.eval('hikUpdateCharacterList()')
    cmds.refresh()


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
