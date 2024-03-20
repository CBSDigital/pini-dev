"""Tools for managing mesh faces."""

from maya import cmds

from pini.utils import single, basic_repr

from . import pom_uv, pom_vertex


class PFace(object):
    """Represents a face on a mesh."""

    def __init__(self, mesh, idx):
        """Constructor.

        Args:
            mesh (PCpntMesh): parent mesh
            idx (int): face index
        """
        self.mesh = mesh
        self.idx = idx

    @property
    def uvs(self):
        """Obtain list of UVs for this face's vertices.

        Returns:
            (PUV list): uvs
        """
        return [_vtx.to_uv() for _vtx in self.vtxs]

    @property
    def vtxs(self):
        """Obtain list of vertices for this face.

        Returns:
            (PVertex list): vertices
        """
        return self.to_vtxs()

    def contains_uv(self, uv):
        """Test whether this face contains the given UV point.

        Args:
            uv (PUV): uv point to test

        Returns:
            (bool): whether contained
        """
        _bbox = pom_uv.PUVBBox(self.uvs)
        return _bbox.contains(uv)

    def to_vtxs(self):
        """Obtain vertices from this face.

        Returns:
            (PVertex list): vertices
        """
        _, _v_str = single(cmds.polyInfo(self, faceToVertex=True)).split(':')
        _v_idxs = [int(_token) for _token in _v_str.split()]
        return [pom_vertex.PVertex(
            idx=_v_idx, mesh=self.mesh) for _v_idx in _v_idxs]

    def __str__(self):
        return '{}.f[{:d}]'.format(self.mesh, self.idx)

    def __repr__(self):
        return basic_repr(self, str(self))
