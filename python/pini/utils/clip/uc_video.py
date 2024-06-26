"""Tools for managing video files (eg. mov, mp4)."""

import logging
import re

from .. import path
from .. import cache
from ..u_misc import single

from . import uc_clip, uc_ffmpeg

_LOGGER = logging.getLogger(__name__)
_VIDEO_FMTS = ['mov', 'mp4', 'avi', 'cine']


class Video(path.MetadataFile, uc_clip.Clip):
    """Represents a video file."""

    def __init__(self, file_):
        """Constructor.

        Args:
            file_ (str): path to file
        """
        super(Video, self).__init__(file_)

        # Check format
        if self.extn and self.extn.lower() not in _VIDEO_FMTS:
            _LOGGER.debug('BAD VIDEO FILE %s', self.path)
            raise ValueError("Bad extension {}".format(self.extn))

    def read_metadata(self):
        """Read metadata for this video.

        Returns:
            ():
        """
        _ffprobe = self._read_ffprobe()

        _data = {}
        _data['dur'] = self._read_dur(ffprobe=_ffprobe)
        _data['fps'] = self._read_fps(ffprobe=_ffprobe)
        _data['size'] = self.size()

        return _data

    def _read_dur(self, ffprobe=None):
        """Read duration of this video.

        Args:
            ffprobe (str): ffprobe reading

        Returns:
            (float): duration in seconds
        """
        _LOGGER.debug('READ DUR %s', self)

        _ffprobe = ffprobe or self._read_ffprobe()

        # Find dur
        _dur_line = single([
            _line for _line in _ffprobe
            if _line.strip().startswith('Duration: ')], catch=True)
        _LOGGER.debug(' - DUR LINE %s', _dur_line)
        if not _dur_line:
            _LOGGER.error('FFPROBE %s', _ffprobe)
            raise RuntimeError(self.path)
        _dur_token, _ = _dur_line.split(', ', 1)
        _LOGGER.debug(' - DUR TOKEN %s', _dur_token)
        _, _dur_str = _dur_token.split()
        _LOGGER.debug(' - DUR STR %s', _dur_str)
        _hrs, _mins, _secs = _dur_str.split(':')
        _dur = 60*60*float(_hrs) + 60*float(_mins) + float(_secs)
        _LOGGER.debug(' - DUR %.03f', _dur)
        return _dur

    @cache.cache_method_to_file
    def _read_ffprobe(self, force=False):
        """Obtain ffprobe reading for this video.

        Args:
            force (bool): force regenerate any cached result

        Returns:
            (str): ffprobe reading
        """
        assert self.exists()
        return uc_ffmpeg.read_ffprobe(self)

    def _read_fps(self, ffprobe=None):
        """Read fps for this video.

        Args:
            ffprobe (str): ffprobe reading

        Returns:
            (float): frame rate
        """
        _LOGGER.debug('READ FPS %s', self)

        _ffprobe = ffprobe or self._read_ffprobe()

        # Find fps
        _stream = single([
            _line for _line in _ffprobe
            if _line.strip().startswith('Stream ') and
            'Video:' in _line], catch=True)
        _LOGGER.debug(' - STREAM %s', _stream)
        if not _stream:
            raise RuntimeError('Invalid video {}'.format(self.path))
        _fps_token = single([
            _token for _token in _stream.split(', ')
            if _token.endswith(' fps')], catch=True)
        _LOGGER.debug(' - FPS TOKEN %s', _fps_token)
        _fps_str, _ = _fps_token.strip().split()
        _fps = float(_fps_str)
        _LOGGER.debug(' - FPS %.03f', _fps)

        return _fps

    def build_thumbnail(self, file_, width=100, frame=None, force=False):
        """Build thumbnail for this video.

        Args:
            file_ (str): thumbnail path
            width (int): thumbnail width in pixels
            frame (int): select frame to export (default is middle frame)
            force (bool): overwrite existing without confirmation
        """
        _res = self._to_thumb_res(width)
        self.to_frame(file_, frame=frame, force=force, res=_res)

    def to_fps(self):
        """Obtain fps of this video.

        Returns:
            (float): frames per second
        """
        return self._read_fps()

    def to_dur(self):
        """Obtain duration of this video.

        Returns:
            (float): duration in seconds
        """
        return self._read_dur()

    def to_frame(self, file_, res=None, frame=None, force=False):
        """Extract a frame of this video to image file.

        Args:
            file_ (File): path to write to
            res (tuple): covert resolution
            frame (int): select frame to export (default is middle frame)
            force (bool): overwrite existing without confirmation

        Returns:
            (File): output image
        """
        return uc_ffmpeg.video_to_frame(
            video=self, file_=file_, force=force, res=res, frame=frame)

    def to_seq(self, seq, fps=None, res=None, force=False, verbose=0):  # pylint: disable=unused-argument
        """Extract frames from this video.

        Args:
            seq (Seq): output sequence
            fps (float): override output frame rate
            res (tuple): override output res
            force (bool): overwrite existing frames without confirmation
            verbose (int): print process data
        """
        _kwargs = locals()
        _kwargs.pop('self')
        return uc_ffmpeg.video_to_seq(video=self, **_kwargs)

    def to_res(self, force=False):
        """Obtain resolution of this video.

        Args:
            force (bool): force regenerate any cached ffprobe result

        Returns:
            (int tuple): width/height
        """
        _ffprobe = self._read_ffprobe(force=force)

        # Find fps
        _stream = single([
            _line for _line in _ffprobe
            if _line.strip().startswith('Stream ') and
            'Video:' in _line], catch=True)
        _LOGGER.debug(' - STREAM %s', _stream)
        if not _stream:
            raise RuntimeError('Invalid video {}'.format(self.path))
        _res_token = single([
            _token for _token in re.split('[ ,]', _stream)
            if _token.count('x') == 1 and
            _token.replace('x', '').isdigit()], catch=True)
        _LOGGER.debug(' - RES TOKEN %s', _res_token)
        return tuple(int(_val) for _val in _res_token.split('x'))
