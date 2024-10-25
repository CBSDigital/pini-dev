"""Tools for managing pipelined references across multiple dccs."""

from pini import dcc

from .pr_base import CPipeRef, to_cmp_str

if dcc.NAME == 'maya':
    from .maya import (
        CMayaAiStandIn, CMayaRef, CMayaShadersRef, lock_cams, CMayaAiVolume,
        apply_grouping, find_pipe_refs, create_ai_standin, create_rs_pxy,
        create_ai_vol, CMayaImgPlaneRef)
elif dcc.NAME == 'nuke':
    from .pr_nuke import CNukeReadRef
elif dcc.NAME == 'hou':
    from .pr_hou import find_pipe_refs
