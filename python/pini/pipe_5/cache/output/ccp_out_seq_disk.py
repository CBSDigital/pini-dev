"""Tools for managing cacheable out sequences objs on a disk pipe."""

import logging

from pini.utils import single, Seq

from . import ccp_out_seq_base

_LOGGER = logging.getLogger(__name__)


class CCPOutputSeqDisk(ccp_out_seq_base.CCPOutputSeqBase):
    """Represents a cacheable out seq on a disk-based pipe."""

    def delete(self, force=False):  # pylint: disable=arguments-differ
        """Delete this output seq and update caches on parent entity.

        Args:
            force (bool): delete files without confirmation
        """
        from ... import cache

        super().delete(force=force)
        self.to_dir().find_seqs(force=True)
        assert isinstance(self.entity, cache.CCPEntity)
        self.entity.find_outputs(force=True)

    def _read_frames(self):
        """Read list of frames.

        This is cached and managed by the parent dir.

        Returns:
            (int list): frames
        """
        _LOGGER.info('READ FRAMES %s', self.path)

        _dir = self.to_dir()
        _LOGGER.info(' - DIR %s', _dir.path)
        _seqs = [_path for _path in _dir.find_seqs(force=True)
                 if isinstance(_path, Seq) and
                 _path.path == self.path]
        _LOGGER.info(' - SEQS %d %s', len(_seqs), _seqs)
        if not _seqs:
            raise OSError(
                'Seq no longer exists (need to update cache on '
                'parent) ' + self.path)
        _seq = single(_seqs)
        _frames = _seq.frames

        return _frames
