"""Tools for managing the wrapper for the MVector object."""

import math

from maya.api import OpenMaya as om

from maya_pini.utils import to_unique
from .. import base


class CVector(base.CArray3, om.MVector):
    """Wrapper for OpenMaya.MVector object."""

    __init__ = om.MVector.__init__

    def angle_to(self, other):
        """Read the angle in degrees between this vector and another one.

        Args:
            other (CVector): target vector

        Returns:
            (float): angle between (in degrees)
        """
        return math.degrees(self.angle(other))

    def bearing(self):
        """Obtain bearing of this vector.

        This is the angle in degrees with +z axis clockwise facing down.

        Returns:
            (float): bearing (in degrees)
        """
        if not self.z:
            _bearing = 270 if self.x > 0 else 90
        else:
            _bearing_r = math.atan(- self.x / self.z)
            _bearing = math.degrees(_bearing_r) % 360
        if self.z < 0:
            _bearing -= 180
            _bearing = _bearing % 360
        return _bearing

    def normalized(self):
        """Get the normalized version of this vector."""
        _dup = CVector(self)
        _dup.normalize()
        return _dup

    def to_curve(self, pos=None, name='vector', col='Red'):
        """Build this vector into a curve.

        Args:
            pos (CPoint): start point
            name (str): name for curve
            col (str): curve colour

        Returns:
            (CNurbsCurve): curve
        """
        from maya_pini import open_maya as pom
        _p0 = pos or pom.CPoint()
        _p1 = _p0 + self
        _crv = pom.CMDS.curve(point=[_p0, _p1], degree=1, name=to_unique(name))
        _crv.set_col(col)
        return _crv

    def __mul__(self, other):
        return CVector(self[0]*other, self[1]*other, self[2]*other)

    def __rxor__(self, other):
        """Obtain cross product of this vector and another one.

        This overloads the caret (^) operator.
        """
        _cross = super().__rxor__(other)
        return CVector(_cross)

    def __xor__(self, other):
        """Obtain cross product of this vector and another one.

        This overloads the caret (^) operator.
        """
        _cross = super().__xor__(other)
        return CVector(_cross)


X_AXIS = CVector(1, 0, 0)
Y_AXIS = CVector(0, 1, 0)
Z_AXIS = CVector(0, 0, 1)
ORIGIN = CVector(0, 0, 0)
