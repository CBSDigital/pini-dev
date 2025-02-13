"""Tools for managing the resolution object."""

from . import u_misc


class Res:
    """Represents a resolution, eg. 640x640."""

    def __init__(self, width, height, name=None):
        """Constructor.

        Args:
            width (int): width (in pixels)
            height (int): height (in pixels)
            name (str): optional name/label for this res
        """
        self.width = int(width)
        self.height = int(height)
        self.name = name

        self.aspect = self.width / self.height
        self.uid = self.width, self.height, self.name
        self.cmp_key = self.width, self.height

    def duplicate(self, name=None, mult=1.0):
        """Duplicate this resolution.

        Args:
            name (str): apply new name
            mult (float): apply multiplication

        Returns:
            (Res): duplicate of this res
        """
        return Res(self.width, self.height, name=name or self.name) * mult

    def to_tuple(self):
        """Convert to tuple.

        Returns:
            (tuple): width/height
        """
        return self.width, self.height

    def __eq__(self, other):
        return self.cmp_key == other.cmp_key

    def __getitem__(self, name):
        if name == 0:
            return self.width
        if name == 1:
            return self.height
        raise AttributeError(name)

    def __hash__(self):
        return hash(self.cmp_key)

    def __lt__(self, other):
        return self.cmp_key < other.cmp_key

    def __mul__(self, val):
        return Res(
            round(self.width * val), round(self.height * val), name=self.name)

    def __str__(self):
        return f'{self.width}x{self.height}'

    def __repr__(self):
        _label = str(self)
        if self.name:
            _label += f'({self.name})'
        return u_misc.basic_repr(self, _label)
