"""Tools for managing output objects."""

from pini.utils import register_custom_yaml_handler

from .cp_out_base import (
    CPOutputBase, OUTPUT_FILE_TYPES, OUTPUT_SEQ_TYPES, OUTPUT_VIDEO_TYPES,
    ver_sort)

from .cp_out_file import CPOutputFile
from .cp_out_seq import CPOutputSeq
from .cp_out_seq_dir import CPOutputSeqDir
from .cp_out_video import CPOutputVideo

from .cp_out_tools import to_output, cur_output

register_custom_yaml_handler(CPOutputFile)
register_custom_yaml_handler(CPOutputVideo)
register_custom_yaml_handler(CPOutputSeq)
