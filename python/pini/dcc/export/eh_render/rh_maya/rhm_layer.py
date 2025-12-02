"""Tools for managing maya render layers."""

import logging

from maya_pini.utils import to_render_extn

from .. import rh_pass

_LOGGER = logging.getLogger(__name__)


class CRenderLayer(rh_pass.CRenderPass):
    """Represents a maya render layer."""

    def __init__(self, layer):
        """Constructor.

        Args:
            layer (pom.CRenderLayer): layer node
        """
        self.layer = layer
        super().__init__(
            node=layer, name=layer.pass_name, extn=to_render_extn())

    @property
    def renderable(self):
        """Obtain renderable status for this node.

        Returns:
            (bool): renderable
        """
        return self.layer.is_renderable()

    def set_renderable(self, renderable):
        """Set renderable status for this layer.

        Args:
            renderable (bool): renderable status to apply
        """
        _LOGGER.debug(' - SET RENDERABLE %s %d', self, renderable)
        self.layer.set_renderable(renderable)
