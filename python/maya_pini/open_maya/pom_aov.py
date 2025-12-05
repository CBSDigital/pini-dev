"""Tools for managing AOVs."""

from pini.utils import single
from maya_pini.utils import cur_renderer

from . import pom_cmds, wrapper


class CAOV(wrapper.CNode):
    """Represents an AOV node."""

    @property
    def name(self):
        """Obtain name of this AOV.

        Returns:
            (str): AOV name
        """
        return self.plug['name'].get_val()


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
        CAOV(_aov) for _aov in pom_cmds.CMDS.ls(type=_type)
        if not _aov.is_referenced()]
