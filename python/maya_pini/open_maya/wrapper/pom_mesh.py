"""Tools for adding functionilty to OpenMaya.MFnMesh object."""

import logging

from maya import cmds
from maya.api import OpenMaya as om

from pini.utils import single, EMPTY
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
        _node = node
        if isinstance(_node, base.CBaseNode):
            _node = str(_node)
        super().__init__(_node)
        _m_dag = to_mdagpath(_node)
        try:
            om.MFnMesh.__init__(self, _m_dag)
        except ValueError as _exc:
            _LOGGER.error(_exc)
            raise ValueError(
                f'Failed to construct MFnMesh object {_node}') from _exc

        # Check shape
        _shp = self.shp
        if not _shp:
            raise ValueError(f'No shape {_node}')
        if _shp.object_type() != 'mesh':
            raise ValueError(f'Bad shape {_shp}')

    @property
    def n_edges(self):
        """Obtain edge count for this mesh.

        Returns:
            (int): edge count
        """
        return self.numEdges

    @property
    def n_faces(self):
        """Obtain face count for this mesh.

        Returns:
            (int): face count
        """
        return cmds.polyEvaluate(self, face=True)

    @property
    def n_vtxs(self):
        """Obtain vertex count for this mesh.

        Returns:
            (int): vertex count
        """
        return self.numVertices

    def closest_n(self, point):
        """Get the normal on this mesh closest to the given point.

        Args:
            point (CPoint): point to test

        Returns:
            (CVector): closest mesh normal
        """
        from maya_pini import open_maya as pom
        _pt, _ = self.getClosestNormal(point, pom.WORLD_SPACE)
        return pom.CVector(_pt)

    def closest_p(self, point):
        """Get the closest point on this mesh to the given point.

        Args:
            point (CPoint): point to test

        Returns:
            (CPoint): closest point on mesh
        """
        from maya_pini import open_maya as pom
        _pt, _ = self.getClosestPoint(point, pom.WORLD_SPACE)
        return pom.CPoint(_pt)

    def is_referenced(self):
        """Check whether this node is referenced.

        Returns:
            (bool): whether referenced
        """
        from maya_pini import open_maya as pom
        return pom.CNode(self).is_referenced()

    def rename(self, name):
        """Rename this mesh.

        (NOTE: also renames the shape node)

        Args:
            name (str): new node name

        Returns:
            (CMesh): updated mesh object
        """
        _new = super().rename(name)
        _new.shp.rename(name + 'Shape')
        return CMesh(_new)

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
        return self.shp.attr[f'e[{idx:d}]']

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
        return self.shp.attr[f'f[{idx:d}]']

    def to_faces(self, idxs=None):
        """Obtain list of faces for this mesh.

        Args:
            idxs (int list): override face indices

        Returns:
            (str list): face attributes
        """
        _idxs = idxs or range(self.n_faces)
        return [self.to_face(_idx) for _idx in _idxs]

    def to_uv(self, idx):
        """Obtain the uv attribute for the given uv index.

        Args:
            idx (int): uv index

        Returns:
            (str): uv (eg. polySphere.map[0])
        """
        return self.shp.attr[f'map[{idx:d}]']

    def to_vtx(self, idx):
        """Obtain the given vertex index of this mesh.

        Args:
            idx (int): vertex index

        Returns:
            (str): vertex attribute
        """
        return self.shp.attr[f'vtx[{idx:d}]']

    def to_vtxs(self):
        """Obtain list of mesh vertices.

        Returns:
            (str list): vertices
        """
        return [self.to_vtx(_idx) for _idx in range(self.numVertices)]


def find_meshes(namespace=EMPTY, referenced=None, class_=None):
    """Find meshes in the current scene.

    Args:
        namespace (str): apply namespace filter
        referenced (bool): filter by referenced state
        class_ (class): override mesh constructor class

    Returns:
        (CMesh list): meshes
    """
    _class = class_ or CMesh
    _meshes = []
    for _shp in cmds.ls(
            type='mesh', noIntermediate=True, allPaths=True, recursive=True):

        _tfm = to_parent(_shp)
        _mesh = _class(_tfm)

        if referenced is not None and referenced != _mesh.is_referenced():
            continue

        if namespace is not EMPTY:
            if not namespace:
                if _mesh.namespace:
                    continue
            else:
                if _mesh.namespace != namespace:
                    continue

        _meshes.append(_mesh)

    return sorted(_meshes)
