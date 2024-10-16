"""Tools for managing cacheable out sequences objs on a sg pipe."""

import logging

from pini.pipe import shotgrid

from . import ccp_out_seq_base
from ..ccp_utils import pipe_cache_to_file

_LOGGER = logging.getLogger(__name__)


class CCPOutputSeqSG(ccp_out_seq_base.CCPOutputSeqBase):
    """Represents a cacheable out seq on a sg-based pipe."""

    def delete(self, force=False):  # pylint: disable=arguments-differ
        """Delete this output seq and update caches on parent entity.

        Args:
            force (bool): delete files without confirmation
        """
        super().delete(force=force)

        _pub_file = shotgrid.SGC.find_pub_file(self)
        _pub_file.omit()
        self.job.find_outputs(force=True)

    @pipe_cache_to_file
    def _read_frames(self):
        """Read list of frames.

        This is cached and managed by the parent dir.

        Returns:
            (int list): frames
        """
        _LOGGER.info('READ FRAMES %s', self.path)
        _LOGGER.info(' - CACHE FMT %s', self.cache_fmt)
        _frames = super()._read_frames()
        return _frames
