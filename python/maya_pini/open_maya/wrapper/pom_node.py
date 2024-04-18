"""Tools for adding functionilty to OpenMaya.MFnDependencyNode object."""

from maya.api import OpenMaya as om

from .. import base
from ..pom_utils import to_mobject


class CNode(base.CBaseNode, om.MFnDependencyNode):
    """Wrapper for OpenMaya.MFnDependencyNode object."""

    def __init__(self, node):
        """Constructor.

        Args:
            node (str): node name (eg. persp)
        """
        super(CNode, self).__init__(node)
        _mobj = to_mobject(node)
        om.MFnDependencyNode.__init__(self, _mobj)


TIME = CNode('time1')
