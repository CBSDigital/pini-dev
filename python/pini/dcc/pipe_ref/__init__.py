"""Tools for managing pipelined references across multiple dccs."""

from pini import dcc

from .pr_base import CPipeRef, to_cmp_str

if dcc.NAME == 'maya':
    from .pr_maya import CMayaAiStandIn, CMayaRef, CMayaShadersRef
elif dcc.NAME == 'nuke':
    from .pr_nuke import CNukeReadRef
elif dcc.NAME == 'hou':
    from .pr_hou import find_pipe_refs
