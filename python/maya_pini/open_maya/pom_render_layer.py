"""Tools for manging render layers."""

import logging

from maya import cmds
from maya.app.renderSetup.model import renderSetup

from pini.utils import single, passes_filter

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
        _cur_name = str(self)
        _node_name = f'rs_{pass_name}'
        _LOGGER.debug(
            'SET PASS NAME %s -> %s %s', _cur_name, pass_name, _node_name)
        self.render_setup_layer.rename(pass_name)
        _LOGGER.debug(
            ' - RENDER SETUP LAYER %s %s', self.render_setup_layer,
            type(self.render_setup_layer))
        self.rename(_node_name)
        self.__init__(_node_name)  # pylint: disable=unnecessary-dunder-call

    def set_renderable(self, renderable=True):
        """Set renderable status of this layer.

        Args:
            renderable (bool): status to apply
        """
        self.plug['renderable'].set_val(renderable)


def create_render_layer(name):
    """Create render layer.

    Args:
        name (str): render layer name

    Returns:
        (CRenderLayer): render layer
    """
    _lyrs = {_lyr.pass_name for _lyr in find_render_layers()}
    if name in _lyrs:
        _LOGGER.info(' - LAYER %s ALREADY EXISTS', name)
        return find_render_layer(name)
    _rs = renderSetup.instance()
    _rs.createRenderLayer(name)
    return find_render_layer(name)


def cur_render_layer():
    """Obtain current render layer.

    Returns:
        (CRenderLayer): current layer
    """
    _crl = cmds.editRenderLayerGlobals(query=True, currentRenderLayer=True)
    return single(_lyr for _lyr in find_render_layers() if _lyr == _crl)


def find_render_layer(match=None, catch=False, **kwargs):
    """Find render layer.

    Args:
        match (str): name to match
        catch (bool): no error if render layer not found

    Returns:
        (CRenderLayer): render layer
    """
    _lyrs = find_render_layers(**kwargs)
    if not match and len(_lyrs) == 1:
        return single(_lyrs)

    _name_match = [
        _lyr for _lyr in _lyrs if match in (_lyr.name, _lyr.pass_name)]
    if len(_name_match) == 1:
        return single(_name_match)

    # Handle fail
    if catch:
        return None
    raise ValueError(match)


def find_render_layers(
        referenced=False, renderable=None, pass_name=None, filter_=None):
    """Find render layers in the current scene.

    Args:
        referenced (bool): filter by referenced status
            (use None to find all render layers)
        renderable (bool): filter by layer renderable status
        pass_name (str): filter by pass name
        filter_ (str): apply pass name filter

    Returns:
        (CRenderLayer list): render layers
    """
    _lyrs = []
    for _lyr in cmds.ls(type='renderLayer'):
        _LOGGER.debug('CHECKING LAYER %s', _lyr)
        _lyr = CRenderLayer(_lyr)
        if not _lyr.pass_name:
            continue
        if pass_name and pass_name != _lyr.pass_name:
            continue
        if referenced is not None and _lyr.is_referenced() != referenced:
            continue
        if renderable is not None and _lyr.is_renderable() != renderable:
            continue
        if filter_ and not passes_filter(_lyr.pass_name, filter_):
            continue
        _lyrs.append(_lyr)

    return _lyrs
