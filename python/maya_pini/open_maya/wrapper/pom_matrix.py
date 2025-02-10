"""Tools for adding functionality to the OpenMaya.MMatrix object."""

from maya import cmds
from maya.api import OpenMaya as om

from pini.utils import basic_repr

from maya_pini.utils import to_unique


class CMatrix(om.MMatrix):
    """Represents a transformation matrix."""

    def apply_to(self, node, world_space=True):
        """Apply this transformtion to the given node.

        Args:
            node (CTransform): node to apply transformation to
            world_space (bool): apply matrix in world or local space
        """
        cmds.xform(node, matrix=self, worldSpace=world_space)

    def to_loc(self, name='matrix', scale=None, col=None):
        """Build a locator and apply this matrix to it.

        Args:
            name (str): locator name
            scale (float): locator scale
            col (str): locator colour

        Returns:
            (CTransform): locator
        """
        _loc = self.to_p().to_loc(name=name, scale=scale, col=col)
        self.apply_to(_loc)
        return _loc

    def to_geo(self, name='matrix', scale=1.0):
        """Build RGB coloured geometry to display this matrix.

        Args:
            name (str): name for geo group
            scale (float): local axes scale

        Returns:
            (CTransform): geometry group
        """
        from maya_pini import open_maya as pom
        _grp = pom.CMDS.group(name=to_unique(name + '_GRP'), empty=True)
        for _col, _axis, _name in [
                ('red', pom.X_AXIS * scale, 'X'),
                ('green', pom.Y_AXIS * scale, 'Y'),
                ('blue', pom.Z_AXIS * scale, 'Z'),
        ]:
            _crv = _axis.to_curve(
                pom.ORIGIN, col=_col, name=to_unique(name + _name))
            _crv.parent(_grp)
        self.apply_to(_grp)

        return _grp

    def to_lx(self):
        """Obtain local X-axis for this matrix.

        Returns:
            (CVector): local x
        """
        from maya_pini import open_maya as pom
        return pom.CVector(self.to_tuple()[: 3])

    def to_ly(self):
        """Obtain local Y-axis for this matrix.

        Returns:
            (CVector): local y
        """
        from maya_pini import open_maya as pom
        return pom.CVector(self.to_tuple()[4: 7])

    def to_lz(self):
        """Obtain local Z-axis for this matrix.

        Returns:
            (CVector): local z
        """
        from maya_pini import open_maya as pom
        return pom.CVector(self.to_tuple()[8: 11])

    def to_p(self):
        """Get position/translation of this matrix.

        Returns:
            (CPoint): position
        """
        from maya_pini import open_maya as pom
        _tfm_mtx = om.MTransformationMatrix(self)
        return pom.CPoint(_tfm_mtx.translation(om.MSpace.kWorld))

    def to_tuple(self):
        """Obtain this matrix as a 16-item tuple.

        Returns:
            (float tuple): 16 values
        """
        return tuple(self[_idx] for _idx in range(16))

    def __repr__(self):
        _vals_s = ', '.join(
            f'{_item:.04f}' for _item in self.to_tuple())
        _label = f'({_vals_s})'
        return basic_repr(self, _label)


IDENTITY = CMatrix()
