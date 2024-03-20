"""Tools for manging render layers."""

import logging

from maya import cmds

from pini.utils import single

from . import wrapper

_LOGGER = logging.getLogger(__name__)


class CRenderLayer(wrapper.CNode):
    """Represents a render layer node."""

    @property
    def pass_name(self):
        """Obtain pass name for this layer.

        Returns:
            (str): pass name
        """
        if self == 'defaultRenderLayer':
            return 'masterLayer'
        _rsl = self.render_setup_layer
        if _rsl:
            return str(_rsl)
        return None

    @property
    def render_setup_layer(self):
        """Obtain renderSetupLayer node.

        This determines pass name.

        Returns:
            (CNode): render setup layer node
        """
        return single(
            self.plug['message'].find_outgoing(
                plugs=False, type_='renderSetupLayer'),
            catch=True)

    def is_renderable(self):
        """Check if this layer is renderable.

        Returns:
            (bool): renderable
        """
        return bool(self.plug['renderable'].get_val())

    def set_pass_name(self, pass_name):
        """Update this layer's pass name.

        Args:
            pass_name (str): pass name to apply
        """
        _node_name = 'rs_'+pass_name
        self.render_setup_layer.rename(pass_name)
        self.rename(_node_name)
        self.__init__(pass_name)  # pylint: disable=unnecessary-dunder-call

    def set_renderable(self, renderable=True):
        """Set renderable status of this layer.

        Args:
            renderable (bool): status to apply
        """
        self.plug['renderable'].set_val(renderable)


def cur_render_layer():
    """Obtain current render layer.

    Returns:
        (CRenderLayer): current layer
    """
    _crl = cmds.editRenderLayerGlobals(query=True, currentRenderLayer=True)
    return single(_lyr for _lyr in find_render_layers() if _lyr == _crl)


def find_render_layers(referenced=False, renderable=None):
    """Find render layers in the current scene.

    Args:
        referenced (bool): filter by referenced status
            (use None to find all render layers)
        renderable (bool): filter by layer renderable status

    Returns:
        (CRenderLayer list): render layers
    """
    _lyrs = []
    for _lyr in cmds.ls(type='renderLayer'):
        _LOGGER.debug('CHECKING LAYER %s', _lyr)
        _lyr = CRenderLayer(_lyr)
        if not _lyr.pass_name:
            continue
        if referenced is not None and _lyr.is_referenced() != referenced:
            continue
        if renderable is not None and _lyr.is_renderable() != renderable:
            continue
        _lyrs.append(_lyr)

    return _lyrs
