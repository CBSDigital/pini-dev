"""Tools for managing human IK."""

import logging

from pini.utils import single

from maya_pini import ui, open_maya as pom

from maya import cmds, mel

_LOGGER = logging.getLogger(__name__)

CHAR_LIST = ui.OptionMenuGrp('hikCharacterList')
SRC_LIST = ui.OptionMenuGrp('hikSourceList')
CONTROL_RIG = 'Control Rig'


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
        if _src == 'Control Rig':
            _result = CONTROL_RIG
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
        if source is None:
            _mel = f'hikEnableCharacter("{self}", false); hikUpdateSourceList()'
        elif isinstance(source, (str, pom.CReference, pom.CNode)):
            _hik = find_hik(source)
            _LOGGER.info(' - HIK %s', _hik)
            _mel = f'mayaHIKsetCharacterInput("{self}", "{_hik}")'
        else:
            raise ValueError(source)
        _LOGGER.info(' - MEL %s', _mel)
        mel.eval(_mel)


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
        _str_hiks = [
            _hik for _hik in _hiks if match in (str(_hik), _hik.namespace)]
        if len(_str_hiks) == 1:
            return single(_str_hiks)

    raise ValueError(match, kwargs)


def find_hiks():
    """Find HIK nodes in this scene.

    Returns:
        (PHIKNode list): HIKs
    """
    refresh_ui()
    _hiks = []
    for _item in CHAR_LIST.get_vals():
        if _item == 'None':
            continue
        _hik = PHIKNode(_item)
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


def set_source(hik, source):
    """Set source for the given HIK system.

    Args:
        hik (str): HIK node to update
        source (str): name of source to apply
    """
    _hik = find_hik(hik)
    _hik.set_source(source)
