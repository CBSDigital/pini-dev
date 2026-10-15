"""Tools for adding functionality to OpenMaya.MFnMesh object."""

import logging

from maya import cmds
from maya.api import OpenMaya as om

from pini.utils import single, EMPTY
from maya_pini.utils import to_parent, to_shp

from . import pom_transform
from .. import base
from ..pom_utils import to_mdagpath

_LOGGER = logging.getLogger(__name__)


class _CMeshShp(base.CBaseDagNode, om.MFnMesh):
    """Wrapper for OpenMaya.MFnMesh object."""

    def __init__(self, shp):
        """Constructor.

        Args:
            shp (str): mesh shape node
        """
        _m_obj = to_mdagpath(shp)
        om.MFnMesh.__init__(self, _m_obj)


class CMesh(pom_transform.CTransform):
    """Wrapper for OpenMaya.MFnMesh object."""

    _shp = None

    def __init__(self, node, shp=None):
        """Constructor.

        Args:
            node (str): mesh transform
            shp (str): force mesh shape
        """
        super().__init__(node)
        self._shp_name = shp or to_shp(str(self), type_='mesh')

    @property
    def shp(self):
        """Obtain shape node for this mesh.

        Returns:
            (CMeshShp): shape
        """
        if not self._shp:
            self._shp = _CMeshShp(self._shp_name)
        return self._shp

    @property
    def n_edges(self):
        """Obtain edge count for this mesh.

        Returns:
            (int): edge count
        """
        return self.shp.numEdges

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
        return self.shp.numVertices

    def closest_n(self, point):
        """Get the normal on this mesh closest to the given point.

        Args:
            point (CPoint): point to test

        Returns:
            (CVector): closest mesh normal
        """
        from maya_pini import open_maya as pom
        _pt, _ = self.shp.getClosestNormal(point, pom.WORLD_SPACE)
        return pom.CVector(_pt)

    def closest_p(self, point):
        """Get the closest point on this mesh to the given point.

        Args:
            point (CPoint): point to test

        Returns:
            (CPoint): closest point on mesh
        """
        from maya_pini import open_maya as pom
        _pt, _ = self.shp.getClosestPoint(point, pom.WORLD_SPACE)
        return pom.CPoint(_pt)

    def instance(self, name=None):
        """Instance this mesh's shape.

        Args:
            name (str): name for instance

        Returns:
            (CTransform): instance transform
        """
        from maya_pini import open_maya as pom
        return pom.CTransform(single(cmds.instance(self.shp, name=name)))

    def rename(self, name):
        """Rename this mesh.

        (NOTE: also renames the shape node)

        Args:
            name (str): new node name

        Returns:
            (CMesh): updated mesh object
        """
        _LOGGER.debug('RENAME %s -> %s', self, name)
        _new = super().rename(name)
        _new.shp.rename(f'{name}Shape')
        return CMesh(_new)

    def p_to_uv(self, point):
        """Get the UV position of the given point on this mesh.

        Args:
            point (CPoint): point to test

        Returns:
            (tuple): UV point
        """
        from maya_pini import open_maya as pom
        _u, _v, _ = self.shp.getUVAtPoint(point, space=pom.WORLD_SPACE)
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
        return [self.to_vtx(_idx) for _idx in range(self.n_vtxs)]


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
