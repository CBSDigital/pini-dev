"""Tools for managing cacheable output video objects."""

# pylint: disable=too-many-ancestors

import logging

from ...elem import CPOutputVideo
from . import ccp_out_file

_LOGGER = logging.getLogger(__name__)


class CCPOutputVideo(CPOutputVideo, ccp_out_file.CCPOutputFile):
    """Represents an output video on disk with built in caching."""

    delete = ccp_out_file.CCPOutputFile.delete
    exists = ccp_out_file.CCPOutputFile.exists
    get_metadata = ccp_out_file.CCPOutputFile.get_metadata
    set_metadata = ccp_out_file.CCPOutputFile.set_metadata

    @property
    def metadata(self):
        """Obtain this output's metadata.

        Returns:
            (dict): metadata
        """
        return self.get_metadata()
