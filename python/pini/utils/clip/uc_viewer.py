"""Tools for managing clip viewers.

This is a 3rd party app for viewing a video or image sequence (clip).

eg. rv, VLC, djv_view
"""

import platform
import logging
import os
import subprocess
import time

from ..cache import cache_result
from ..path import File, abs_path
from ..u_exe import find_exe
from ..u_misc import single, system

_LOGGER = logging.getLogger(__name__)


class _Viewer:
    """Base class for any viewer."""

    NAME = None

    PLAYS_VIDEOS = True
    PLAYS_SEQS = True
    PLAYS_AUDIO = True

    @property
    def exe(self):
        """Obtain this viewer's executable.

        Returns:
            (File|None): executable (if any)
        """
        assert self.NAME
        return find_exe(self.NAME)

    def view(self, clip_, fps=None):
        """View the given clip (to be implemented in subclass).

        Args:
            clip_ (Clip): clip to view
            fps (float): apply frame rate
        """
        raise NotImplementedError

    def __repr__(self):
        return f'<Viewer:{self.NAME}>'


class _DjvView(_Viewer):
    """Represents djv_view app."""

    NAME = 'djv_view'

    PLAYS_AUDIO = False

    def view(self, clip_, fps=None):
        """View the given clip in djv_view.

        Args:
            clip_ (Clip): clip to view
            fps (float): apply frame rate
        """
        from .. import clip

        if fps:
            _LOGGER.warning('UNUSED FPS ARG %s', fps)

        # Build cmds
        if isinstance(clip_, clip.Seq):
            _path = clip_.path.replace("%04d", "#")
        else:
            _file = File(clip_)
            assert _file.exists()
            _path = _file.path
        _cmds = [self.exe.path, _path]

        # Execute
        _LOGGER.info('VIEW CLIP %s', ' '.join(_cmds))
        if isinstance(clip_, clip.Video):
            subprocess.Popen(_cmds, env={}, shell=True)
        elif isinstance(clip_, clip.Seq):
            system(_cmds, result=False, block_shell_window=False)
        else:
            raise ValueError(clip_)


class _DJV(_Viewer):
    """Represents djv app."""

    NAME = 'djv'

    PLAYS_AUDIO = True

    def view(self, clip_, fps=None):
        """View the given clip in djv_view.

        Args:
            clip_ (Clip): clip to view
            fps (float): apply frame rate
        """
        from .. import clip
        if fps:
            _LOGGER.warning('UNUSED FPS ARG %s', fps)
        if isinstance(clip_, clip.Seq):
            _path = clip_.path.replace("%04d", "#")
        else:
            _file = File(clip_)
            assert _file.exists()
            _path = _file.path
        _cmds = [self.exe.path, _path]
        _LOGGER.info('VIEW CLIP %s', ' '.join(_cmds))
        system(_cmds, result=False)


class _MPlay(_Viewer):
    """Represents houdini mplay tool."""

    NAME = 'mplay'

    PLAYS_VIDEOS = False

    def view(self, clip_, fps=None):
        """View the given clip in mplay.

        Args:
            clip_ (Clip): clip to view
            fps (float): apply frame rate
        """
        from .. import clip
        if fps:
            raise NotImplementedError
        _LOGGER.info('MPLAY CLIP %s', clip_)
        _LOGGER.info(' - EXE %s', self.exe)
        _cmds = [self.exe]
        if isinstance(clip_, clip.Seq):
            _start, _end = clip_.to_range()
            _path = clip_.path.replace('.%04d.', '.$F4.')
            _cmds += ['-f', _start, _end, 1]
        elif isinstance(clip_, clip.Video):
            raise ValueError('Mplay cannot play videos')
        else:
            raise ValueError(clip_)
        _LOGGER.info(' - PATH %s', _path)
        _cmds += [_path]
        system(_cmds, result=False, verbose=1)


class _RV(_Viewer):
    """Represents rv app."""

    NAME = 'rv'

    def view(self, clip_, fps=None):
        """View the given clip in rv.

        Args:
            clip_ (Clip): clip to view
            fps (float): apply frame rate
        """
        assert self.exe
        _cmds = [self.exe.path]
        if fps:
            _cmds += ['-fps', str(fps)]
        _cmds += [clip_.path, '-play']
        # system(_cmds, verbose=1, result=False)
        _LOGGER.info('VIEW CLIP %s', ' '.join(_cmds))
        subprocess.Popen(_cmds)


class _VLC(_Viewer):
    """Represents VLC app."""

    NAME = 'vlc'
    PLAYS_SEQS = False

    def view(self, clip_, fps=None):
        """View the given clip in VLC.

        Args:
            clip_ (Clip): clip to view
            fps (float): not applicable
        """
        from .. import clip
        if isinstance(clip_, clip.Seq):
            raise ValueError(clip_)
        if fps:
            _LOGGER.warning('UNUSED FPS ARG %s', fps)
        _file = File(clip_)
        assert _file.exists()
        assert self.exe
        _path = abs_path(_file.path, win=platform.system() == 'Windows')
        _cmds = [self.exe.path, _path]
        _LOGGER.info('VIEW CLIP %s', ' '.join(_cmds))
        subprocess.Popen(_cmds)


class _WMPlayer(_Viewer):
    """Represents Windows Media Player (legacy) app."""

    NAME = 'wmplayer'
    PLAYS_SEQS = False

    def view(self, clip_, fps=None):
        """View the given clip in VLC.

        Args:
            clip_ (Clip): clip to view
            fps (float): not applicable
        """
        from .. import clip
        if isinstance(clip_, clip.Seq):
            raise ValueError(clip_)
        if fps:
            _LOGGER.warning('UNUSED FPS ARG %s', fps)
        _file = File(clip_)
        assert _file.exists()
        assert self.exe
        _path = abs_path(_file.path, win=platform.system() == 'Windows')
        _cmds = [self.exe.path, _path]
        _LOGGER.info('VIEW CLIP %s', ' '.join(_cmds))
        subprocess.Popen(_cmds)


def find_viewer(name=None, plays_seqs=None, plays_videos=None):
    """Find a viewer on this machine.

    Args:
        name (str): name for viewer - if no name is passed then
            $PINI_VIEWER is used
        plays_seqs (bool): filter by ability to play image sequences
        plays_videos (bool): filter by ability to play videos

    Returns:
        (Viewer): matching viewer
    """
    _name = name or os.environ.get('PINI_VIEWER')
    _viewers = find_viewers(plays_seqs=plays_seqs, plays_videos=plays_videos)
    if not _viewers:
        return None
    if not _name:
        return sorted(_viewers, key=_viewer_sort)[0]

    # Match by name
    _match = single([_viewer for _viewer in _viewers if _viewer.NAME == _name],
                    catch=True)
    if _match:
        return _match
    if name:
        raise ValueError('Failed to find viewer ' + name)
    return _viewers[0]


def find_viewers(plays_seqs=None, plays_videos=None):
    """Find viewers avaiable on this machine.

    Args:
        plays_seqs (bool): filter by ability to play image sequences
        plays_videos (bool): filter by ability to play videos

    Returns:
        (Viewer list): matching viewers
    """
    _viewers = _read_viewers()
    _LOGGER.debug('FIND VIEWERS %s', _viewers)
    if plays_seqs is not None:
        _viewers = [
            _viewer for _viewer in _viewers
            if _viewer.PLAYS_SEQS == plays_seqs]
        _LOGGER.debug(' - FILTERED BY PLAYS SEQS %s', _viewers)
    if plays_videos is not None:
        _viewers = [
            _viewer for _viewer in _viewers
            if _viewer.PLAYS_VIDEOS == plays_videos]
        _LOGGER.debug(' - FILTERED BY PLAYS VIDEOS %s', _viewers)
    return _viewers


@cache_result
def _read_viewers():
    """Read available viewers on this machine.

    Returns:
        (Viewer list): viewers
    """
    _start = time.time()
    _viewers = []
    for _class in [_DjvView, _DJV, _RV, _VLC, _MPlay, _WMPlayer]:
        _viewer = _class()
        _LOGGER.debug(' - TESTING %s %s', _viewer, _viewer.exe)
        if not _viewer.exe:
            _LOGGER.debug('   - REJECTED %s %d', _viewer.exe, bool(_viewer.exe))
            continue
        _viewers.append(_viewer)
    _LOGGER.debug(
        'READ %d VIEWERS IN %.01fs', len(_viewers), time.time() - _start)
    return tuple(_viewers)


def _viewer_sort(viewer):
    """Sort viewers.

    Args:
        viewer (Viewer): viewer to sort

    Returns:
        (tuple): sort key
    """
    _rank = {'rv': 0,
             'djv_view': 75,
             'djv': 100}
    return _rank.get(viewer.NAME, 50), viewer.NAME
