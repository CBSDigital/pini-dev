"""Tools for managing video files (eg. mov, mp4)."""

import logging
import re
import time

from . import uc_clip

from .. import path
from .. import cache
from ..u_exe import find_exe
from ..u_misc import single, system, nice_age

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
        _ffprobe_exe = find_exe('ffprobe')
        assert _ffprobe_exe
        _path = self.path
        _cmds = [_ffprobe_exe.path, _path]
        _LOGGER.debug(' - CMD %s', ' '.join(_cmds))
        _result = system(_cmds, result='err', decode='latin-1')
        _lines = [_line.strip() for _line in _result.split('\n')]

        return _lines

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

    def to_frame(self, file_, force=False):
        """Extract a frame of this video to image file.

        Args:
            file_ (File): path to write to
            force (bool): overwrite existing without confirmation

        Returns:
            (File): output image
        """
        _LOGGER.info('TO FRAMES %s', self.path)
        _img = path.File(file_)
        _img.delete(force=force)
        _img.test_dir()

        _time = self.to_dur()/2
        _LOGGER.info(' - TIME %f', _time)

        # Build ffmpeg commands
        _ffmpeg = find_exe('ffmpeg')
        _cmds = [
            _ffmpeg,
            '-ss', _time,
            '-i', self,
            '-frames:v', 1,
            _img]
        assert not _img.exists()
        _out, _err = system(_cmds, result='out/err', verbose=1)
        if not _img.exists():
            _LOGGER.info('OUT %s', _out)
            _LOGGER.info('ERR %s', _err)
            raise RuntimeError('Failed to export image '+_img.path)

        return _img

    def to_frames(self, seq, fps=None, force=False):
        """Extract frames from this video.

        Args:
            seq (Seq): output sequence
            fps (float): override output frame rate
            force (bool): overwrite existing frames without confirmation
        """
        from pini.utils import clip
        _LOGGER.info('TO FRAMES %s', self.path)
        _LOGGER.info(' - TARGET %s', seq.path)

        _fps = fps or self.to_fps()
        _LOGGER.info(' - FPS %s', _fps)

        # Check output seq
        assert isinstance(seq, clip.Seq)
        seq.delete(force=force)
        seq.test_dir()

        # Build ffmpeg commands
        _ffmpeg = find_exe('ffmpeg')
        _cmds = [
            _ffmpeg,
            '-i', self,
            '-r', _fps,
            seq]
        _start = time.time()
        _out, _err = system(_cmds, result='out/err', verbose=1)
        seq.to_frames(force=True)
        if not seq.exists():
            _LOGGER.info('OUT %s', _out)
            _LOGGER.info('ERR %s', _err)
            raise RuntimeError('Failed to compile seq '+seq.path)

        _f_start, _f_end = seq.to_range()
        _LOGGER.info(' - WROTE FRAMES %d-%d IN %s', _f_start, _f_end,
                     nice_age(time.time() - _start))

        return seq

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
