"""Tools for managing image files."""

import logging
import re

from .path import File
from .clip import find_ffmpeg_exe
from .u_misc import single, system
from . import u_res

_LOGGER = logging.getLogger(__name__)


class Image(File):
    """Represents an image file on disk."""

    def convert(self, file_, size=None, catch=False, force=False):
        """Convert this image to a different format.

        Args:
            file_ (File): target file
            size (Res): apply resize
            catch (bool): no error if conversion fails
            force (bool): overwrite existsing without confirmation
        """
        from pini import qt
        _file = File(file_)
        assert _file != self
        _LOGGER.info('CONVERT %s -> %s', self.extn, _file.extn)
        _fmts = {self.extn.lower(), _file.extn.lower()}
        if self.extn == _file.extn and not size:
            self.copy_to(_file, force=force)
        elif 'exr' in _fmts:
            _colspace = {
                ('exr', 'jpg'): 'iec61966_2_1',
            }.get((self.extn, _file.extn))
            _convert_file_ffmpeg(
                self, _file, colspace=_colspace, size=size,
                catch=catch, force=force)
        elif 'iff' in _fmts:
            _LOGGER.info(' - SRC %s', self.path)
            _LOGGER.info(' - TRG %s', _file.path)
            raise RuntimeError('IFF is not supported')
        elif not _fmts - set(qt.PIXMAP_EXTNS):
            _convert_file_qt(self, _file, size=size, force=force)
        else:
            raise NotImplementedError(f'Convert {self.extn} -> {_file.extn}')
        return Image(_file)

    def to_aspect(self):
        """Obtain aspect ration of this image.

        Returns:
            (float): aspect ratio
        """
        return self.to_res().aspect

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
        _ffprobe_exe = find_ffmpeg_exe(exe='ffprobe')
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
            _LOGGER.warning(' - FAILED TO PARSE FFPROBE %s', self.path)
            if catch:
                return None
            raise RuntimeError(f'Invalid image {self.path}')

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
            raise RuntimeError(f'Failed to read res {self.path}')
        _res = tuple(int(_token) for _token in _res_token.split('x'))

        return u_res.Res(*_res)

    def _read_res_qt(self):
        """Read this image's resolution using qt.

        Returns:
            (tuple): width/height
        """
        from pini import qt
        _pix = qt.CPixmap(self.path)
        return u_res.Res(_pix.width(), _pix.height())


def _convert_file_ffmpeg(
        src, trg, colspace=None,  size=None, catch=False, force=False):
    """Convert image file to a different format using ffmpeg.

    Args:
        src (File): source file
        trg (File): output file
        colspace (str): apply colourspace via -apply_trc flag
        size (Res): apply resize
        catch (bool): no error if conversion fails
        force (bool): replace existing without confirmation
    """
    _ffmpeg = find_ffmpeg_exe()
    _cmds = [_ffmpeg]
    if colspace:
        _cmds += ['-apply_trc', colspace]
    _cmds += ['-i', src]
    if size:
        _cmds += ['-vf', f'scale={size.width}:{size.height}']
    _cmds += [trg]

    trg.delete(force=force, wording='Replace')
    assert not trg.exists()
    trg.to_dir().mkdir()
    system(_cmds, verbose=1)

    if not trg.exists():
        _msg = 'Failed to generate image '+trg.path
        if not catch:
            raise RuntimeError(_msg)
        _LOGGER.warning(_msg)


def _convert_file_qt(src, trg, size=None, force=False):
    """Convert image file to a different format using qt.

    Args:
        src (File): source file
        trg (File): output file
        size (Res): apply resize
        force (bool): replace existing without confirmation
    """
    _LOGGER.debug(' - CONVERT FILE QT %s', src)
    from pini import qt
    trg.delete(force=force, wording='replace')
    _pix = qt.CPixmap(src)
    if size:
        _pix = _pix.resize(size)
        _LOGGER.debug(' - APPLY SIZE %s %s', size, _pix.size())
    _pix.save_as(trg)
