"""Tools for managing and viewing clips: image sequences or videos."""

from .uc_clip import Clip
from .uc_seq import Seq, find_seqs, file_to_seq, CacheSeq, to_seq
from .uc_viewer import find_viewers, find_viewer
from .uc_video import Video, VIDEO_EXTNS
from .uc_ffmpeg import play_sound, find_ffmpeg_exe
