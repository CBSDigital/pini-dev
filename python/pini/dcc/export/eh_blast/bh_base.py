"""Tools for managing the base blast handler."""

import logging
import os

from pini import qt, pipe, icons
from pini.tools import error

from .. import eh_base

_LOGGER = logging.getLogger(__name__)


class CBlastHandler(eh_base.CExportHandler):
    """Base class for any blast handler."""

    NAME = 'Blast Tool'
    TYPE = 'Blast'
    ACTION = 'Blast'
    ICON = icons.find('Collision')

    _manual_range_elems = None
    add_range = True

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
        super().build_ui(version_up=False)

    def _add_custom_ui_elems(self):
        """Add custom ui elements."""
        self.ui.add_separator()
        _vid_fmt = os.environ.get('PINI_VIDEO_FORMAT', 'mp4')
        self.ui.add_combo_box(
            'Format', items=[_vid_fmt, 'jpg', 'png'])

        self.ui.add_separator()
        self.ui.add_check_box(
            'ForceReplace', label='Replace existing without confirmation')
        self.ui.add_check_box(
            'View', label='View blast on completion', val=True)
        self.ui.add_check_box(
            'Burnins', val=True, label='Add burnins on video compile')
        self.ui.add_check_box(
            'DisableSave', val=False, label='Disable save on blast (unsafe)',
            save_policy=qt.SavePolicy.SAVE_IN_SCENE, tooltip=(
                'Disabling save on blast is unsafe as you may get animation '
                'that does not have a scene file approved'))

    def init_export(self):
        """Initiate export."""
        super().init_export()

        # Check blast template
        self._template = self.work.find_template('blast', catch=True)
        if not self._template:
            qt.notify(
                f'No blast template found in this job:\n\n{self.work}\n\n'
                f'Unable to blast.',
                title='Warning', parent=self.parent)
            return

        self._set_camera()
        self._set_output_name()

    def _set_camera(self):
        """Apply camera."""
        raise NotImplementedError

    def _set_output_name(self):
        """Apply output name."""
        _output_name = self.settings['output_name']
        if _output_name == '<camera>':
            assert self.camera
            _output_name = str(self.camera).replace(':', '_')

        if not pipe.is_valid_token(
                _output_name, job=self.work.job, token='output_name'):
            raise error.HandledError(
                f'You have chosen "{_output_name}" as the output name '
                f'which is not valid within the pipeline.\n\nPlease select '
                f'another output name.')

        self.output_name = _output_name

    def exec_from_ui(self, **kwargs):
        """Execute blast using settings from ui."""
        _LOGGER.debug('EXEC FROM UI')
        _kwargs = self.ui.to_kwargs()
        _kwargs.update(kwargs)
        _LOGGER.debug(' - KWARGS (A) %s', _kwargs)
        if 'disable_save' in _kwargs:
            _kwargs['save'] = not _kwargs.pop('disable_save')
            _LOGGER.debug(' - KWARGS (B) %s', _kwargs)
        return super().exec_from_ui(ui_kwargs=_kwargs)
