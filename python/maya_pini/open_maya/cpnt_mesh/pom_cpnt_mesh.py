"""Tools for managing the component mesh."""

import logging

from .. wrapper import CMesh
from . import pom_uv, pom_vertex, pom_face

_LOGGER = logging.getLogger(__name__)


class PCpntMesh(CMesh):
    """Represents a mesh with access to its components."""

    @property
    def faces(self):
        """Obtain list of faces for this mesh.

        Returns:
            (PFace list): faces
        """
        _faces = []
        for _f_idx in range(self.n_faces):
            _face = pom_face.PFace(idx=_f_idx, mesh=self)
            _faces.append(_face)
        return _faces

    @property
    def vtxs(self):
        """Obtain list of vertices for this mesh.

        Returns:
            (PVertex list): vertices
        """
        _vtxs = []
        for _v_idx in range(self.n_vtxs):
            _vtx = pom_vertex.PVertex(idx=_v_idx, mesh=self)
            _vtxs.append(_vtx)
        return _vtxs

    def p_to_uv(self, point):
        """Map a point in space to a UV value.

        Args:
            point (CPoint): point to test

        Returns:
            (PUV): UV value
        """
        _result = super(PCpntMesh, self).p_to_uv(point)
        return pom_uv.to_uv(_result)

    def to_uv_bbox(self):
        """Obtain UV bounding box for this mesh.

        Returns:
            (PUVBBox): bounding box
        """
        _uvs = [_vtx.to_uv() for _vtx in self.vtxs]
        return pom_uv.PUVBBox(_uvs)

    def uv_to_p(self, uv):
        """Find a point in space from the given UV position.

        Args:
            uv (PUV): UV point to test

        Returns:
            (CPoint): point in 3D space
        """
        from maya_pini import open_maya as pom

        _uv = pom_uv.to_uv(uv)
        _faces = [_face for _face in self.faces if _face.contains_uv(_uv)]
        _face = _faces[0]
        _LOGGER.debug(' - FACE %s', _face)
        _result = self.getPointAtUV(
            _face.idx, _uv.u, _uv.v, space=pom.WORLD_SPACE)
        return pom.to_p(_result)
