"""Tools for managing cacheable output sequence objects."""

import logging

from ... import elem
from . import ccp_out_base, ccp_out_seq_dir
from ..ccp_utils import pipe_cache_on_obj, pipe_cache_to_file

_LOGGER = logging.getLogger(__name__)


class CCPOutputSeqBase(elem.CPOutputSeq, ccp_out_base.CCPOutputBase):
    """Represents an output sequence on disk with built in caching."""

    get_metadata = ccp_out_base.CCPOutputBase.get_metadata
    set_metadata = ccp_out_base.CCPOutputBase.set_metadata
    strftime = ccp_out_base.CCPOutputBase.strftime

    @pipe_cache_on_obj
    def mtime(self):
        """Obtain mtime for this sequence.

        Returns:
            (float): mtime
        """
        _metadata_mtime = self.metadata.get('mtime')
        if _metadata_mtime:
            return _metadata_mtime
        return super().mtime()

    @pipe_cache_on_obj
    def owner(self):
        """Obtain owner of this sequence.

        Returns:
            (str): owner
        """
        _metadata_owner = self.metadata.get('owner')
        if _metadata_owner:
            return _metadata_owner
        return super().owner()

    def to_dir(self):  # pylint: disable=arguments-differ
        """Obtain this output sequence's parent dir.

        Returns:
            (CCPOutputSeqDir): output sequence dir
        """
        assert self._dir
        assert isinstance(self._dir, ccp_out_seq_dir.CCPOutputSeqDir)
        return self._dir

    @pipe_cache_to_file
    def to_res(self):
        """Obtain res for this image sequence.

        Returns:
            (tuple): width/height
        """
        return super().to_res()
