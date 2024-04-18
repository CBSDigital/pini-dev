"""Tools for managing direct wrappers of OpenMaya objects."""

from maya.api import OpenMaya as om

from .pom_point import CPoint
from .pom_vector import CVector, X_AXIS, Y_AXIS, Z_AXIS, ORIGIN

from .pom_bounding_box import CBoundingBox, to_bbox

from .pom_anim_curve import CAnimCurve
from .pom_camera import (
    CCamera, active_cam, find_cams, set_render_cam, find_render_cam, find_cam)
from .pom_matrix import CMatrix, IDENTITY
from .pom_mesh import CMesh, find_meshes
from .pom_nurbs_curve import CNurbsCurve
from .pom_node import CNode, TIME
from .pom_plug import (
    CPlug, plus_plug, minus_plug, selected_plugs, to_plug, selected_plug)
from .pom_transform import CTransform
from .pom_reference import (
    CReference, find_ref, find_refs, create_ref, obtain_ref, selected_ref)

WORLD_SPACE = om.MSpace.kWorld
