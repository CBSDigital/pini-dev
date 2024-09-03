"""Tools for managing cacheable output sequence directory objects."""

import logging
import sys

from ..ccp_utils import pipe_cache_to_file, pipe_cache_on_obj
from ...elem import CPOutputSeqDir

_LOGGER = logging.getLogger(__name__)


class CCPOutputSeqDir(CPOutputSeqDir):
    """Represents an output sequence directory.

    This object is used to avoid reread long lists of frames. The first
    time the dir is searched for sequences, the result is cached and
    is only reread if the cache is rebuilt

    Rebuilding is triggered by the CCPWorkFile.find_outputs list being
    force refreshed (since this object is not easily accessible).
    """

    @property
    def cache_fmt(self):
        """Obtain cache format string for storing image dir data.

        Returns:
            (str): cache format
        """
        from pini import pipe
        _ver = pipe.VERSION
        return self.to_file(
            f'.pini/{{func}}_P{_ver:d}+{sys.platform}.pkl').path

    def find_outputs(self, force=False):
        """Find outputs within this sequence directory.

        Args:
            force (bool): force reread from disk

        Returns:
            (CCPOutputSeq list): outputs
        """
        _LOGGER.debug('FIND OUTPUTS force=%d %s', force, self)
        if force:
            self.find_seqs(force=True)
        _outs = self._read_outputs(force=force)
        _LOGGER.debug(' - FIND OUTPUTS force=%d n_outs=%d %s', force,
                      len(_outs), self)
        return _outs

    @pipe_cache_on_obj
    def _read_outputs(
            self, output_seq_class=None, output_video_class=None, force=False):
        """Read outputs within this sequence directory.

        Args:
            output_seq_class (class): override output seq class
            output_video_class (class): override output video class
            force (bool): force rebuild output objects

        Returns:
            (CCPOutputSeq list): outputs
        """
        from ... import cache

        _LOGGER.debug('READ OUTPUTS %s', self)
        _output_seq_class = output_seq_class or cache.CCPOutputSeq
        _output_video_class = output_video_class or cache.CCPOutputVideo
        _out_seqs = super()._read_outputs(
            output_seq_class=_output_seq_class,
            output_video_class=_output_video_class)
        _LOGGER.debug(' - READ OUTPUTS %s seqs=%d', self, len(_out_seqs))
        return _out_seqs

    @pipe_cache_to_file
    def find_seqs(self, force=False, **kwargs):
        """Find file sequences within this dir.

        Args:
            force (bool): force reread from disk

        Returns:
            (Seq|File list): matching seqs
        """
        assert not kwargs
        _seqs = super().find_seqs(
            include_files=True, depth=2)
        _LOGGER.debug('FIND SEQS force=%d n_seqs=%d %s', force,
                      len(_seqs), self)
        return _seqs
