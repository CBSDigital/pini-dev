"""Wrapper maya.api.OpenMaya module which adds functionality.

Notes:
 - nodes should raise ValueError if construction fails


Issues:
 - would be nicer to use pom.cmds not pom.CMDS
 - str mapping is broken by getitem overload
   ie. cmds.objectType(_node) does not work so that _node['tx'] works
"""

from .base import CBaseNode, CArray3, CBaseTransform
from .wrapper import (
    CCamera, CMesh, CNode, CPlug, CTransform, CPoint, CNurbsCurve,
    CVector, X_AXIS, Y_AXIS, Z_AXIS, ORIGIN, CBoundingBox, to_bbox,
    CAnimCurve, CMatrix, WORLD_SPACE, find_meshes, plus_plug, minus_plug,
    CReference, find_ref, find_refs, create_ref, active_cam, obtain_ref,
    selected_plugs, to_plug, find_cams, set_render_cam, find_render_cam,
    find_cam, selected_plug, IDENTITY, selected_ref, TIME)

from .pom_cmds import CMDS
from .pom_utils import (
    to_mobject, get_selected, set_loc_scale, to_node, to_mesh, to_m, to_tfm,
    to_p, set_to_geos, set_to_tfms, cast_node, add_anim_offs, find_nodes,
    selected_node, create_loc)

from .pom_joint import CJoint
from .pom_skeleton import (
    CSkeleton, find_skeletons, find_skeleton, selected_skeleton)
from .pom_render_layer import (
    find_render_layers, CRenderLayer, cur_render_layer, find_render_layer,
    create_render_layer)

from .cpnt_mesh import PCpntMesh, to_uv, PUV, to_vtx

LOC_SCALE = 1.0
