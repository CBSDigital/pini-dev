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
    LABEL = 'Render handler'
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

    def set_settings(self, **kwargs):
        """Setup settings dict."""
        super().set_settings(snapshot=False, **kwargs)

    def exec_from_ui(self, ui_kwargs=None, **kwargs):
        """Execuate this export using settings from ui.

        Args:
            ui_kwargs (dict): override interface kwargs
        """
        _ui_kwargs = ui_kwargs or self.ui.to_kwargs()
        if 'range_' in _ui_kwargs:
            _rng = _ui_kwargs.pop('range_')
            _start, _end = _rng
            _frames = list(range(_start, _end + 1))
            _ui_kwargs['frames'] = _frames
        return super().exec_from_ui(ui_kwargs=_ui_kwargs, **kwargs)
