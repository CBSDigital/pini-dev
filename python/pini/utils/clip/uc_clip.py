"""Tools for managing the base class for any clip.

A clip is a video or an image sequence.
"""

# pylint: disable=no-member

import logging
import os

_LOGGER = logging.getLogger(__name__)


class Clip(object):
    """Base class for any video or image sequence."""

    path = None

    def build_thumbnail(self, file_, width=100, force=False):
        """Build thumbnail for this clip.

        Args:
            file_ (str): thumbnail path
            width (int): thumbnail width in pixels
            force (bool): overwrite existing without confirmation
        """
        raise NotImplementedError

    def _to_thumb_res(self, width):
        """Calculate thumbnail res.

        Args:
            width (int): required width

        Returns:
            (tuple): thumbnail width/height
        """
        _cur_res = self.to_res()
        if not _cur_res:
            raise RuntimeError(self)
        _aspect = 1.0 * _cur_res[0] / _cur_res[1]
        _thumb_res = width, int(width/_aspect)
        _LOGGER.info(' - RES %s -> %s', _cur_res, _thumb_res)
        return _thumb_res

    def view(self, viewer=None):
        """View this clip.

        Args:
            viewer (str): force viewer
        """
        from .. import clip
        _seq = _video = None
        if isinstance(self, clip.Seq):
            _seq = True
        elif isinstance(self, clip.Video):
            _video = True
        else:
            raise ValueError(self)

        _viewer = clip.find_viewer(
            viewer, plays_seqs=_seq, plays_videos=_video)
        _LOGGER.info(' - VIEWER %s', _viewer)
        if _viewer:
            _viewer.view(self)
        else:
            os.startfile(self.path)
