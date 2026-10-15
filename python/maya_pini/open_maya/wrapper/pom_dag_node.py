"""Tools for adding functionality to OpenMaya.MFnDagNode object."""

from maya.api import OpenMaya as om

from .. import base, pom_utils


class CDagNode(base.CBaseDagNode, om.MFnDagNode):
    """Wrapper for OpenMaya.MFnDagNode object."""

    def __init__(self, node):
        """Constructor.

        Args:
            node (str): node to build dag node from
        """
        _m_dag = pom_utils.to_mdagpath(node)
        om.MFnDagNode.__init__(self, _m_dag)
