"""Tools for managing image files."""

import logging
import re

from .path import File
from .u_exe import find_exe
from .u_misc import single, system

_LOGGER = logging.getLogger(__name__)


class Image(File):
    """Represents an image file on disk."""

    def to_aspect(self):
        """Obtain aspect ration of this image.

        Returns:
            (float): aspect ratio
        """
        _width, _height = self.to_res()
        return 1.0 * _width / _height

    def to_res(self, catch=True):
        """Read resolution of this image using ffprobe.

        Args:
            catch (bool): no error if fail to read res

        Returns:
            (tuple): width/height
        """
        _LOGGER.debug('TO RES %s', self.path)

        if not self.exists():
            raise OSError('Missing file '+self.path)
        if self.extn.lower() in ['mp4']:
            if catch:
                return None
            raise RuntimeError('Bad image extension '+self.path)

        if self.extn.lower() in ['png', 'jpg', 'jpeg']:
            return self._read_res_qt()
        return self._read_res_ffprobe(catch=catch)

    def _read_ffprobe(self):
        """Read ffprobe result for this image.

        Returns:
            (str list): ffprobe result lines
        """
        _ffprobe_exe = find_exe('ffprobe')
        assert _ffprobe_exe
        _cmds = [_ffprobe_exe.path, self.path]
        _LOGGER.debug(' - CMD %s', ' '.join(_cmds))
        _result = system(_cmds, result='err')
        _lines = [_line.strip() for _line in _result.split('\n')]
        return _lines

    def _read_res_ffprobe(self, catch=True):
        """Read this image's resolution using ffprobe.

        Args:
            catch (bool): no error if fail to read res

        Returns:
            (tuple): width/height
        """
        _ffprobe = self._read_ffprobe()

        # Find stream data
        _stream = single([
            _line.strip() for _line in _ffprobe
            if _line.strip().startswith('Stream ')], catch=True)
        if not _stream:
            if catch:
                return None
            raise RuntimeError('Invalid image {}'.format(self.path))

        # Parse stream
        _LOGGER.debug(' - STREAM %s', _stream)
        _tokens = re.split('[ ,]', _stream)
        _LOGGER.debug(' - TOKENS %s', _tokens)
        _res_token = single([
            _token for _token in _tokens
            if _token.count('x') == 1 and
            _token.replace('x', '').isdigit()], catch=True)
        if (
                not _res_token and
                'decoding for stream 0 failed' in '\n'.join(_ffprobe)):
            return None
        if not _res_token:
            if catch:
                return None
            raise RuntimeError('Failed to read res {}'.format(self.path))
        _res = tuple(int(_token) for _token in _res_token.split('x'))

        return _res

    def _read_res_qt(self):
        """Read this image's resolution using qt.

        Returns:
            (tuple): width/height
        """
        from pini import qt
        _pix = qt.CPixmap(self.path)
        return _pix.width(), _pix.height()
