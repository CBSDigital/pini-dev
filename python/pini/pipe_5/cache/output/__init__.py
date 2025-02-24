"""Tools for managing cacheable output objects."""

from .ccp_out_base import CCPOutputBase, OUTPUT_MEDIA_CONTENT_TYPES
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
