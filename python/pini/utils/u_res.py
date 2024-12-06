"""Tools for managing the resolution object."""

from . import u_misc


class Res:
    """Represents a resolution, eg. 640x640."""

    def __init__(self, width, height):
        """Constructor.

        Args:
            width (int): width (in pixels)
            height (int): height (in pixels)
        """
        self.width = width
        self.height = height

    def to_tuple(self):
        """Convert to tuple.

        Returns:
            (tuple): width/height
        """
        return self.width, self.height

    def __eq__(self, other):
        return self.to_tuple() == other.to_tuple()

    def __getitem__(self, name):
        if name == 0:
            return self.width
        if name == 1:
            return self.height
        raise AttributeError(name)

    def __hash__(self):
        return hash(str(self))

    def __lt__(self, other):
        return self.to_tuple() < other.to_tuple()

    def __mul__(self, val):
        return Res(round(self.width*val), round(self.height*val))

    def __str__(self):
        return f'{self.width}x{self.height}'

    def __repr__(self):
        return u_misc.basic_repr(self, str(self))