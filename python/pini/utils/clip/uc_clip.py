"""Tools for managing the base class for any clip.

A clip is a video or an image sequence.
"""

# pylint: disable=no-member

import logging
import os

_LOGGER = logging.getLogger(__name__)


class Clip:
    """Base class for any video or image sequence."""

    path = None

    def build_thumbnail(self, file_, width=100, frame=None, force=False):
        """Build thumbnail for this video.

        Args:
            file_ (str): thumbnail path
            width (int): thumbnail width in pixels
            frame (int): select frame to export (default is middle frame)
            force (bool): overwrite existing without confirmation
        """
        raise NotImplementedError

    def _to_thumb_res(self, width, catch=False):
        """Calculate thumbnail res.

        Args:
            width (int): required width
            catch (bool): no error if fail to read res

        Returns:
            (tuple): thumbnail width/height
        """
        _cur_res = self.to_res()
        if not _cur_res:
            _LOGGER.warning(' - FAILED TO READ RES %s', self.path)
            if catch:
                return None
            raise RuntimeError(self)
        if width is None:
            return _cur_res
        _aspect = 1.0 * _cur_res[0] / _cur_res[1]
        _thumb_res = width, int(width / _aspect)
        _LOGGER.debug(' - RES %s -> %s', _cur_res, _thumb_res)
        return _thumb_res

    def view(self, viewer=None, start_frame=None):
        """View this clip.

        Args:
            viewer (str): force viewer
            start_frame (int): override start frame
        """
        from .. import clip
        from pini.utils import Video

        _seq = _video = None
        if isinstance(self, clip.Seq):
            _seq = True
        elif isinstance(self, (clip.Video, Video)):
            _video = True
        else:
            raise ValueError(self)

        _viewer = clip.find_viewer(
            viewer, plays_seqs=_seq, plays_videos=_video)
        _LOGGER.info(' - VIEWER %s', _viewer)
        if _viewer:
            _viewer.view(self, start_frame=start_frame)
        else:
            os.startfile(self.path)
