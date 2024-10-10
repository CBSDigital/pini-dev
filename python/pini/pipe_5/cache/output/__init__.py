"""Tools for managing cacheable output objects."""

from pini.utils import register_custom_yaml_handler

from .ccp_out_base import CCPOutputBase
from .ccp_out_file import CCPOutputFile
from .ccp_out_video import CCPOutputVideo
from .ccp_out_seq_dir import CCPOutputSeqDir
from .ccp_out_ghost import CCPOutputGhost

from ... import MASTER

if MASTER == 'disk':
    from .ccp_out_seq_disk import CCPOutputSeqDisk as CCPOutputSeq
elif MASTER == 'shotgrid':
    from .ccp_out_seq_sg import CCPOutputSeqSG as CCPOutputSeq
else:
    raise ValueError(MASTER)

register_custom_yaml_handler(CCPOutputFile)
