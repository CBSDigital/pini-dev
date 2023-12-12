"""Tools for adding functionilty to OpenMaya.MFnTransform object."""

from maya.api import OpenMaya as om

from .. import base
from ..pom_utils import to_mobject


class CTransform(base.CBaseTransform, om.MFnTransform):
    """Wrapper for OpenMaya.MFnTransform object."""

    def __init__(self, node):
        """Constructor.

        Args:
            node (str): node to build transform from
        """
        super(CTransform, self).__init__(node)
        _mobj = to_mobject(node)
        om.MFnTransform.__init__(self, _mobj)
