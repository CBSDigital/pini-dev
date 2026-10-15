"""Tools for adding functionality to OpenMaya.MFnTransform object."""

from maya.api import OpenMaya as om

from .. import base, pom_utils


class CTransform(base.CBaseTransform, om.MFnTransform):
    """Wrapper for OpenMaya.MFnTransform object."""

    def __init__(self, node):
        """Constructor.

        Args:
            node (str): node to build transform from
        """
        _m_dag = pom_utils.to_mdagpath(node)
        om.MFnTransform.__init__(self, _m_dag)
