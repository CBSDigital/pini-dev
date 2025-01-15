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
    ACTION = 'Render'
    TYPE = 'Render'

    def __init__(self, priority=50, label_w=60):
        """Constructor.

        Args:
            priority (int): sort priority (higher priority handlers
                are sorted to top of option lists)
            label_w (int): label width in ui
        """
        super().__init__(label_w=label_w, priority=priority)

    def render(self, frames=None):
        """Execute render - to be implemented in child class.

        Args:
            frames (int list): list of frames to render
        """
        raise NotImplementedError
