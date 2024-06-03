"""Tools for managing mesh UVs."""

import six

from maya import cmds

from pini.utils import basic_repr


def to_uv(uv):
    """Build a UV object.

    Args:
        uv (float tuple): UV values

    Returns:
        (PUV): UV container
    """
    if isinstance(uv, PUV):
        return uv
    if isinstance(uv, six.string_types):
        _vals = cmds.polyEditUV(uv, query=True)
        return PUV(_vals)
    return PUV(uv)


class PUV(object):
    """Represents a mesh UV value."""

    def __init__(self, uv):
        """Constructor.

        Args:
            uv (float tuple): UV values
        """
        self.u, self.v = uv

    def __repr__(self):
        return basic_repr(self, '({:.04f}, {:.04f})'.format(self.u, self.v))


class PUVBBox(object):
    """Represents a bounding box in UV space."""

    def __init__(self, uvs):
        """Constructor.

        Args:
            uvs (PUV list): UVs to include in bounding box
        """
        self.min = PUV((1, 1))
        self.max = PUV((0, 0))
        assert uvs
        for _uv in uvs:
            if _uv.u > self.max.u:
                self.max.u = _uv.u
            if _uv.u < self.min.u:
                self.min.u = _uv.u
            if _uv.v > self.max.v:
                self.max.v = _uv.v
            if _uv.v < self.min.v:
                self.min.v = _uv.v

    @property
    def height(self):
        """Obtain height of this bbox (v-axis).

        Returns:
            (float): bbox height
        """
        return self.max.v - self.min.v

    @property
    def width(self):
        """Obtain width of this bbox (u-axis).

        Returns:
            (float): bbox width
        """
        return self.max.u - self.min.u

    def contains(self, uv):
        """Test whether the given UV point is contained in this bbox.

        Args:
            uv (PUV): UV point to test

        Returns:
            (bool): whether point falls within this bbox
        """
        return (
            uv.u >= self.min.u and
            uv.u <= self.max.u and
            uv.v >= self.min.v and
            uv.v <= self.max.v)

    def expand(self, dist):
        """Expand this bbox by the given distance.

        Args:
            dist (float): distance to expand by
        """
        self.min = to_uv([self.min.u-dist, self.min.v-dist])
        self.max = to_uv([self.max.u+dist, self.max.v+dist])

    def __repr__(self):
        _label = '({:.04f}, {:.04f}) -> ({:.04f}, {:.04f})'.format(
            self.min.u, self.min.v, self.max.u, self.max.v)
        return basic_repr(self, _label)
