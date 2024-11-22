"""Tools for managing the wrapper for the MPoint object."""

from maya.api import OpenMaya as om

from .. import base


class CPoint(base.CArray3, om.MPoint):
    """Wrapper for OpenMaya.MPoint object."""

    __init__ = om.MPoint.__init__

    def __neg__(self):
        return CPoint(-self.x, -self.y, -self.z)

    def __sub__(self, other):
        from maya_pini import open_maya as pom
        _result = super().__sub__(other)
        return pom.CVector(_result)
