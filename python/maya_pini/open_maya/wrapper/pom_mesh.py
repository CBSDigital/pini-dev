"""Tools for adding functionilty to OpenMaya.MFnMesh object."""

import logging

from maya import cmds
from maya.api import OpenMaya as om

from pini.utils import single
from maya_pini.utils import to_parent

from .. import base
from ..pom_utils import to_mdagpath

_LOGGER = logging.getLogger(__name__)


class CMesh(base.CBaseTransform, om.MFnMesh):
    """Wrapper for OpenMaya.MFnMesh object."""

    def __init__(self, node):
        """Constructor.

        Args:
            node (str): mesh transform node (eg. pSphere1)
        """
        super(CMesh, self).__init__(node)
        _m_dag = to_mdagpath(node)
        try:
            om.MFnMesh.__init__(self, _m_dag)
        except ValueError as _exc:
            _LOGGER.error(_exc)
            raise ValueError(
                'Failed to construct MFnMesh object {}'.format(node))

    def closest_p(self, point):
        """Get the closest point on this mesh to the given point.

        Args:
            point (CPoint): point to test

        Returns:
            (CPoint): closest point on mesh
        """
        from maya_pini import open_maya as pom
        _pt, _ = self.getClosestPoint(point, pom.WORLD_SPACE)
        # print _pt
        return pom.CPoint(_pt)

    def p_to_uv(self, point):
        """Get the UV position of the given point on this mesh.

        Args:
            point (CPoint): point to test

        Returns:
            (tuple): UV point
        """
        from maya_pini import open_maya as pom
        _u, _v, _ = self.getUVAtPoint(point, space=pom.WORLD_SPACE)
        return _u, _v

    def to_create(self):
        """Find the create node for this mesh.

        eg. pSphere1 -> polySphere1

        Returns:
            (CNode): create node
        """
        for _type in ['polySphere']:
            _create = single(
                self.shp.find_incoming(
                    plugs=False, type_=_type, connections=False),
                catch=True)
            if _create:
                return _create
        raise ValueError

    def to_edge(self, idx):
        """Obtain the edge attribute for the given edge index.

        Args:
            idx (int): edge index

        Returns:
            (str): edge (eg. polySphere.e[0])
        """
        return self.shp.attr['e[{:d}]'.format(idx)]

    def to_edges(self, idxs=None):
        """Obtain the edge attributes.

        Args:
            idxs (int list): list of edges to return

        Returns:
            (str list): edge list
        """
        _idxs = idxs or range(self.numEdges)
        return [self.to_edge(_idx) for _idx in _idxs]

    def to_face(self, idx):
        """Obtain the face attribute for the given face index.

        Args:
            idx (int): face index

        Returns:
            (str): face (eg. polySphere.f[0])
        """
        return self.shp.attr['f[{:d}]'.format(idx)]

    def to_uv(self, idx):
        """Obtain the uv attribute for the given uv index.

        Args:
            idx (int): uv index

        Returns:
            (str): uv (eg. polySphere.map[0])
        """
        return self.shp.attr['map[{:d}]'.format(idx)]

    def to_vtx(self, idx):
        """Obtain the given vertex index of this mesh.

        Args:
            idx (int): vertex index

        Returns:
            (str): vertex attribute
        """
        return self.shp.attr['vtx[{:d}]'.format(idx)]

    def to_vtxs(self):
        """Obtain list of mesh vertices.

        Returns:
            (str list): vertices
        """
        return [self.to_vtx(_idx) for _idx in range(self.numVertices)]


def find_meshes():
    """Find meshes in the current scene.

    Returns:
        (CMesh list): meshes
    """
    _meshes = []
    for _shp in cmds.ls(type='mesh', noIntermediate=True, allPaths=True):
        _tfm = to_parent(_shp)
        _mesh = CMesh(_tfm)
        _meshes.append(_mesh)
    return _meshes
