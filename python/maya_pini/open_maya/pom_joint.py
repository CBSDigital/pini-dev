"""Tools for managing joints."""

from . import wrapper


class CJoint(wrapper.CTransform):
    """Represents a joint node."""

    @property
    def side(self):
        """Get side of this joint.

        Returns:
            (str): L/R/C
        """
        if 'left' in str(self).lower():
            return 'L'
        if 'right' in str(self).lower():
            return 'R'
        return 'C'

    def set_radius(self, radius):
        """Set joint radius.

        Args:
            radius (float): radius to apply
        """
        self.plug['radius'].set_val(radius)
