"""Tools for managing AOVs."""

import logging

from maya import cmds, mel

from pini.utils import single, to_camel
from maya_pini.utils import cur_renderer

from . import pom_cmds, wrapper

_LOGGER = logging.getLogger(__name__)


class CAOV(wrapper.CNode):
    """Represents an AOV node."""

    def __init__(self, node, type_):
        """Constructor.

        Args:
            node (str): node name
            type_ (str): AOV node type
        """
        super().__init__(node)
        self.type_ = type_

    @property
    def name(self):
        """Obtain name of this AOV.

        Returns:
            (str): AOV name
        """
        _strip = ''
        if self.type_ == 'RedshiftAOV':
            _plug = self.plug['aovType']
        elif self.type_ == 'VRayRenderElement':
            _plug = self.plug['vrayClassType']
            _strip = 'Channel'
        else:
            _plug = self.plug['name']
        _name = _plug.get_val()
        if _strip:
            if _name.endswith(_strip):
                _name = _name[:-len(_strip)]
        return _name


def create_aov(type_, name=None):
    """Create the given AOV.

    Args:
        type_ (str): AOV type
        name (str): AOV name (if required)
    """
    _LOGGER.debug('CREATE AOV %s %s', type_, name)
    _aovs = {_aov.name for _aov in find_aovs()}
    if type_ in _aovs:
        _LOGGER.info(' - AOV %s ALREADY EXISTS', type_)
        return

    _ren = cur_renderer()
    _LOGGER.debug(' - RENDERER %s', _ren)
    if _ren == 'arnold':
        from mtoa import aovs

        cmds.lockNode('initialParticleSE', lock=False, lockUnpublished=False)

        _LOGGER.info('ADD AOV %s type=%s', name, type_)
        _api = aovs.AOVInterface()
        _match = (
            "setAttr: The attribute 'initialParticleSE.aiCustomAOVs[0]"
            ".aovName' is locked or connected and cannot be modified.")
        try:
            _api.addAOV(name, aovType=type_)
        except RuntimeError as _exc:
            _exc = str(_exc).strip()
            if _exc != _match:
                _LOGGER.info(' - ERROR "%s"', _exc)
                _LOGGER.info(' - MATCH "%s"', _match)
                raise _exc

    elif _ren == 'redshift':
        cmds.rsCreateAov(type=type_)
        mel.eval('redshiftUpdateActiveAovList')

    elif _ren == 'vray':
        _create_vray_aov(type_)
    else:
        raise NotImplementedError(_ren)


def _create_vray_aov(type_):
    """Create vray AOV.

    Args:
        type_ (str): AOV type
    """

    # Determina channel name for mel cmds
    if type_ == 'selfIllum' or type_.islower():
        _chan_name = type_
    else:
        _chan_name = to_camel(type_)
    if type_ != 'samplerInfo':
        _chan_name += 'Channel'
    _LOGGER.debug(' - CHAN NAME %s', _chan_name)
    _mel = f'vrayAddRenderElement {_chan_name}'

    # Exec mel
    cmds.select(None)
    _result = mel.eval(_mel)
    _LOGGER.debug(' - MEL "%s"', _mel)
    _node = single(pom_cmds.CMDS.ls(selection=True))

    if not _node:
        raise RuntimeError(type_)

    # Update node settings
    if type_ == 'Sampler Info':
        _node.plug['vray_name_samplerinfo'].set_val('Point')
    elif type_ == 'Z-depth':
        _node.plug['vray_depthFromCamera_zdepth'].set_val(True)
        _node.plug['vray_filtering_zdepth'].set_val(False)

    return _node


def find_aov(name, catch=True):
    """Find aov by name.

    Args:
        name (str): name to match
        catch (bool): no error if no matching AOV found

    Returns:
        (CAOV|None): matching AOV (if any)
    """
    return single(
        [_aov for _aov in find_aovs() if _aov.name == name], catch=catch)


def find_aovs():
    """Find aovs in the current scene.

    Returns:
        (CNode list): aovs
    """

    _ren = cur_renderer()
    if _ren == 'arnold':
        _type = 'aiAOV'
    elif _ren == 'redshift':
        _type = 'RedshiftAOV'
    elif _ren == 'vray':
        _type = 'VRayRenderElement'
    else:
        raise NotImplementedError(_ren)
    return [
        CAOV(_aov, type_=_type) for _aov in pom_cmds.CMDS.ls(type=_type)
        if not _aov.is_referenced()]
