"""Tools for managing dag objects."""

from . import pom_base_node


class CBaseDagNode(pom_base_node.CBaseNode):
    """Base class to underlie all dag object classes."""

    def __str__(self):
        return self.partialPathName()
