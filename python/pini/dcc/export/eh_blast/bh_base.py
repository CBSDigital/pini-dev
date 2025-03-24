"""Tools for managing the base blast handler."""

import logging
import os

from pini import qt

from .. import eh_base

_LOGGER = logging.getLogger(__name__)


class CBlastHandler(eh_base.CExportHandler):
    """Base class for any blast handler."""

    NAME = 'Blast Tool'
    LABEL = 'Playblasts the current scene'
    TYPE = 'Blast'
    ACTION = 'Blast'

    _manual_range_elems = None

    def __init__(self, label_w=60):
        """Constructor.

        Args:
            label_w (int): label width in ui
        """
        super().__init__(label_w=label_w)

    def _callback__Format(self):
        _fmt = self.ui.Format.currentText()
        self.ui.Burnins.setVisible(_fmt in ('mp4', 'mov'))

    def build_ui(self):
        """Build ui elements."""
        self.ui.add_separator_elem()

        self.ui.add_range_elems()
        _vid_fmt = os.environ.get('PINI_VIDEO_FORMAT', 'mp4')
        self.ui.add_combobox_elem(
            'Format', items=[_vid_fmt, 'jpg', 'png'])
        self.ui.add_separator_elem()

        self.ui.add_checkbox_elem(
            'Force', label='Replace existing without confirmation')
        self.ui.add_checkbox_elem(
            'View', label='View blast on completion')
        self.ui.add_checkbox_elem(
            'Burnins', val=True, label='Add burnins on video compile')
        self.ui.add_checkbox_elem(
            'DisableSave', val=False, label='Disable save on blast (unsafe)',
            save_policy=qt.SavePolicy.SAVE_IN_SCENE, tooltip=(
                'Disabling save on blast is unsafe as you may get animation '
                'that does not have a scene file approved'))
        self.ui.add_separator_elem()

    def blast(self):
        """Execute blast."""
        raise NotImplementedError
