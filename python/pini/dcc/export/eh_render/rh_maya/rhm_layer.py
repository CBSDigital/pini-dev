"""Tools for managing maya render layers."""

import logging

from maya_pini import open_maya as pom
from maya_pini.utils import to_render_extn

from .. import rh_pass

_LOGGER = logging.getLogger(__name__)


class CRenderLayer(rh_pass.CRenderPass):
    """Represents a maya render layer."""

    def __init__(self, node):
        """Constructor.

        Args:
            node (pom.CRenderLayer): layer node
        """
        assert isinstance(node, pom.CBaseNode)
        super().__init__(node=node, extn=to_render_extn())
        assert isinstance(self.node, pom.CBaseNode)

    @property
    def name(self):
        """Obtain pass name for this layer.

        Returns:
            (str): pass name
        """
        return self.node.pass_name

    @property
    def renderable(self):
        """Obtain renderable status for this node.

        Returns:
            (bool): renderable
        """
        return self.node.is_renderable()

    def _set_name(self, name):
        """Set pass name for this layer.

        Args:
            name (str): name to apply
        """
        self.node.set_pass_name(name)

    def set_renderable(self, renderable):
        """Set renderable status for this layer.

        Args:
            renderable (bool): renderable status to apply
        """
        _LOGGER.debug(' - SET RENDERABLE %s %d', self, renderable)
        self.node.set_renderable(renderable)

    def _set_name(self, name):
        """Set pass name for this layer.

        Args:
            name (str): name to apply
        """
        self.node.set_pass_name(name)
