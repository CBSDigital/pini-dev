"""Tools for managing the base Render Handler class.

A render handler is a plugin to facilitate rendering to pipeline
by a dcc.
"""

import logging

from .. import eh_base

_LOGGER = logging.getLogger(__name__)


class CRenderHandler(eh_base.CExportHandler):
    """Base class for any render handler."""

    NAME = None
    ACTION = 'render'
    LABEL_WIDTH = 60

    def render(self, frames=None):
        """Execute render - to be implemented in child class.

        Args:
            frames (int list): list of frames to render
        """
        raise NotImplementedError
