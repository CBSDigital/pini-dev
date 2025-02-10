"""Tools for managing the component mesh."""

import logging

from .. wrapper import CMesh
from . import cpt_uv, cpt_vertex, cpt_face

_LOGGER = logging.getLogger(__name__)


class PCpntMesh(CMesh):
    """Represents a mesh with access to its components."""

    @property
    def faces(self):
        """Obtain list of faces for this mesh.

        Returns:
            (PFace list): faces
        """
        return self.to_faces()

    @property
    def vtxs(self):
        """Obtain list of vertices for this mesh.

        Returns:
            (PVertex list): vertices
        """
        return self.to_vtxs()

    def p_to_uv(self, point):
        """Map a point in space to a UV value.

        Args:
            point (CPoint): point to test

        Returns:
            (PUV): UV value
        """
        _result = super().p_to_uv(point)
        return cpt_uv.to_uv(_result)

    def to_faces(self, idxs=None):
        """Obtain list of faces for this mesh.

        Args:
            idxs (int list): override face indices

        Returns:
            (str list): face attributes
        """
        _idxs = idxs or range(self.n_faces)
        _faces = []
        for _f_idx in _idxs:
            _face = cpt_face.PFace(idx=_f_idx, mesh=self)
            _faces.append(_face)
        return _faces

    def to_uv_bbox(self):
        """Obtain UV bounding box for this mesh.

        Returns:
            (PUVBBox): bounding box
        """
        _uvs = self.to_uvs()
        return cpt_uv.PUVBBox(_uvs)

    def to_uvs(self):
        """Obtain list of uvs for this mesh.

        Returns:
            (PUV list): uvs
        """
        return [_vtx.to_uv() for _vtx in self.vtxs]

    def to_vtx(self, idx):
        """Obtain a vertex from this mesh.

        Args:
            idx (int): vertex index

        Returns:
            (PVertex): vertex
        """
        return cpt_vertex.PVertex(idx=idx, mesh=self)

    def to_vtxs(self, idxs=None):
        """Obtain list of vertices from this mesh.

        Args:
            idxs (int list): override list of indices

        Returns:
            (PVertex list): vertices
        """
        _vtxs = []
        for _v_idx in range(idxs or self.n_vtxs):
            _vtx = self.to_vtx(_v_idx)
            _vtxs.append(_vtx)
        return _vtxs

    def uv_to_p(self, uv):
        """Find a point in space from the given UV position.

        Args:
            uv (PUV): UV point to test

        Returns:
            (CPoint): point in 3D space
        """
        from maya_pini import open_maya as pom

        _uv = cpt_uv.to_uv(uv)
        _faces = [_face for _face in self.faces if _face.contains_uv(_uv)]
        if not _faces:
            raise RuntimeError(uv)
        _face = _faces[0]
        _LOGGER.debug(' - FACE %s', _face)
        _result = self.getPointAtUV(
            _face.idx, _uv.u, _uv.v, space=pom.WORLD_SPACE)
        return pom.to_p(_result)
