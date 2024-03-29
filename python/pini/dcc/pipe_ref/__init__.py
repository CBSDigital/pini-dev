"""Tools for managing pipelined references across multiple dccs."""

from pini import dcc

from .pr_base import CPipeRef, to_cmp_str

if dcc.NAME == 'maya':
    from .pr_maya import CMayaAiStandIn, CMayaReference, CMayaLookdevRef
elif dcc.NAME == 'nuke':
    from .pr_nuke import CNukeReadRef
