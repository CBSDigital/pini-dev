"""Tools for managing the CacheSeq object."""

import logging

from . import uc_seq
from ..cache import cache_method_to_file

_LOGGER = logging.getLogger(__name__)


class CacheSeq(uc_seq.Seq):
    """Sequence object which caches frame range to disk."""

    @property
    def cache_fmt(self):
        """Obtain cache format (caches to .pini subdir).

        Returns:
            (str): cache format
        """
        _path = f'{self.dir}/.pini/{self.base}_{self.extn}_{{func}}.pkl'
        return _path

    @cache_method_to_file
    def to_frames(self, force=False):
        """Obtain list of frames.

        Args:
            force (bool): force reread frames from disk

        Returns:
            (int list): frames
        """
        return super().to_frames(force=force)
