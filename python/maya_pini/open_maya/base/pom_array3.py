"""Tools for managing the 3D array base class."""

from maya import cmds

from maya_pini.utils import to_unique, to_clean


class CArray3:
    """Base class for any 3D array object (eg. CPoint, CVector)."""

    def apply_to(self, obj):
        """Apply this data to the given object's translation in world space.

        Args:
            obj (str): node to apply translation to
        """
        from maya_pini import open_maya as pom
        _tfm = pom.to_tfm(obj)
        cmds.xform(_tfm, worldSpace=True, translation=self.to_tuple())

    def move(self, obj, relative=True):
        """Apply this data to the given object.

        ie. apply this data as a move

        Args:
            obj (str): object to move
            relative (bool): apply move as relative
        """
        cmds.move(self.x, self.y, self.z, obj, relative=relative)

    def pformat(self):
        """Get a nicely formatted string of this array's values.

        Returns:
            (str): formatted value string
        """
        _vals = self.to_tuple()
        _str = f'<{_vals[0]:.01f}, {_vals[1]:.02f}, {_vals[2]:.01f}>'
        return _str

    def to_loc(self, name='point', scale=None, col=None):
        """Build a locator at this point in space.

        Args:
            name (str): location name
            scale (float): locator scale
            col (str): locator colour

        Returns:
            (CTransform): locator
        """
        from maya_pini import open_maya as pom

        # Build loc
        _name = to_unique(name)
        _loc = pom.CMDS.spaceLocator(name=_name)
        if _loc.shp != str(_loc) + "Shape":
            cmds.rename(_loc.shp, to_clean(str(_loc) + "Shape"))
        self.apply_to(_loc)

        # Apply col
        if col:
            _loc.set_col(col)

        # Apply scale
        _scale = pom.LOC_SCALE if scale is None else scale
        if scale != 1.0:
            _loc.shp.plug['localScale'].set_val([_scale] * 3)

        return _loc

    def to_tuple(self):
        """Get values of this array.

        Returns:
            (tuple): x/y/z values
        """
        return self.x, self.y, self.z  # pylint: disable=no-member

    def __add__(self, other):
        from maya_pini import open_maya as pom
        _result = super().__add__(other)  # pylint: disable=no-member
        return pom.CVector(_result)

    def __div__(self, other):
        _result = super().__div__(other)  # pylint: disable=no-member
        return self.__class__(_result)

    def __repr__(self):
        _type = type(self).__name__
        return f'<{_type}({self.x:.03f}, {self.y:.03f}, {self.z:.03f})>'  # pylint: disable=no-member
