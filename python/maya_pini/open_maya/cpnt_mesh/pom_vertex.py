"""Tools for managing mesh vertices."""

from pini.utils import basic_repr

from . import pom_uv


def to_vtx(vtx):
    """Build a vertex object.

    Args:
        vtx (str): vertex name (eg. pSphere1.vtx[1])

    Returns:
        (PVertex): vertex
    """
    from maya_pini import open_maya as pom
    _mesh, _idx = vtx.strip(']').split('.vtx[')
    return PVertex(idx=int(_idx), mesh=pom.PCpntMesh(_mesh))


class PVertex(object):
    """Represents a mesh vertex."""

    def __init__(self, mesh, idx):
        """Constructor.

        Args:
            mesh (PCpntMesh): parent mesh
            idx (int): vertex index
        """
        self.mesh = mesh
        self.idx = idx

    def to_uv(self):
        """Get this vertex's UV position.

        Returns:
            (PUV): uv
        """
        return pom_uv.PUV(self.mesh.getUV(self.idx))

    def __str__(self):
        return '{}.vtx[{:d}]'.format(self.mesh, self.idx)

    def __repr__(self):
        return basic_repr(self, str(self))
