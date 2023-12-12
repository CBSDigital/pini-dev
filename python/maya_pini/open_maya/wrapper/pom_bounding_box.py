"""Tools for managing the wrapper for the MBoundingBox object."""

import sys

from maya import cmds
from maya.api import OpenMaya as om


class CBoundingBox(om.MBoundingBox):
    """Represents a bounding box."""

    @property
    def base(self):
        """Obtain centre of base of this box.

        Returns:
            (CPoint): base centre
        """
        from maya_pini import open_maya as pom
        return pom.CPoint(self.center.x, self.min.y, self.center.z)

    @property
    def max(self):
        """Obtain max point.

        Returns:
            (CPoint): max
        """
        from maya_pini import open_maya as pom
        _max = super(CBoundingBox, self).max
        return pom.CPoint(_max)

    @property
    def min(self):
        """Obtain min point.

        Returns:
            (CPoint): min
        """
        from maya_pini import open_maya as pom
        _min = super(CBoundingBox, self).min
        return pom.CPoint(_min)

    @property
    def size(self):
        """Obtain bbox size.

        Returns:
            (CVector): size
        """
        return self.max - self.min

    def to_cube(self):
        """Build a cube representing this bounding box.

        Returns:
            (CMesh): cube
        """
        from maya_pini import open_maya as pom
        _cube = pom.CMDS.polyCube()
        pom.CPoint(0.5, 0.5, 0.5).apply_to(_cube)
        _cube.flush()
        self.min.apply_to(_cube)
        _cube.scale.set_val(self.size)
        return _cube


def to_bbox(obj):
    """Obtain bounding box for the given object.

    Args:
        obj (str): object to read

    Returns:
        (CBoundingBox): bounding box
    """
    from maya_pini import open_maya as pom

    if obj and isinstance(obj, list) and isinstance(obj[0], pom.CPoint):
        _min = pom.CPoint(sys.maxsize, sys.maxsize, sys.maxsize)
        _max = pom.CPoint(0, 0, 0)
        for _pt in obj:
            _min = pom.CPoint(min(_min.x, _pt.x),
                              min(_min.y, _pt.y),
                              min(_min.z, _pt.z))
            _max = pom.CPoint(max(_max.x, _pt.x),
                              max(_max.y, _pt.y),
                              max(_max.z, _pt.z))
    else:
        _result = cmds.exactWorldBoundingBox(
            obj, calculateExactly=True, ignoreInvisible=True)
        _min = pom.CPoint(_result[:3])
        _max = pom.CPoint(_result[-3:])

    return CBoundingBox(_min, _max)
