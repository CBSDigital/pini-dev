"""Tools for managing cacheable output video objects."""

# pylint: disable=too-many-ancestors

import logging

from ...elem import CPOutputVideo
from . import ccp_out_file

_LOGGER = logging.getLogger(__name__)


class CCPOutputVideo(CPOutputVideo, ccp_out_file.CCPOutput):
    """Represents an output video on disk with built in caching."""

    get_metadata = ccp_out_file.CCPOutput.get_metadata
    set_metadata = ccp_out_file.CCPOutput.set_metadata
    delete = ccp_out_file.CCPOutput.delete
    exists = ccp_out_file.CCPOutput.exists
