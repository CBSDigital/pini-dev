"""Tools for managing the base class for any clip.

A clip is a video or an image sequence.
"""

import logging
import os

_LOGGER = logging.getLogger(__name__)


class Clip(object):
    """Base class for any video or image sequence."""

    path = None

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
