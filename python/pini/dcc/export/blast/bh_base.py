"""Tools for managing the base blast handler."""

import logging
import os

from pini import dcc, qt, icons
from pini.qt import QtWidgets, Qt

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
        super(CBlastHandler, self).__init__(label_w=label_w)

    def _build_range_elems(self):
        """Build range elements.

        The allow the range to be manually set.
        """
        _start, _end = dcc.t_range()
        _width = 40

        self.ui.Range = self.add_combobox_elem(
            'Range', items=['From timeline', 'Manual'])

        self.ui.RangeManStart = QtWidgets.QSpinBox()
        self.ui.RangeManStart.setObjectName('RangeManStart')
        self.ui.RangeManStart.setMaximum(10000)
        self.ui.RangeManStart.setValue(_start)
        self.ui.RangeManStart.setButtonSymbols(QtWidgets.QSpinBox.NoButtons)
        self.ui.RangeManStart.setFixedWidth(_width)
        self.ui.RangeManStart.setAlignment(Qt.AlignCenter)
        self.ui.RangeLayout.addWidget(self.ui.RangeManStart)

        self.ui.RangeManLabel = QtWidgets.QLabel('to')
        self.ui.RangeManLabel.setObjectName('RangeManLabel')
        self.ui.RangeManLabel.setFixedWidth(21)
        self.ui.RangeManLabel.setAlignment(Qt.AlignCenter)
        self.ui.RangeLayout.addWidget(self.ui.RangeManLabel)

        self.ui.RangeManEnd = QtWidgets.QSpinBox()
        self.ui.RangeManEnd.setObjectName('RangeManEnd')
        self.ui.RangeManEnd.setMaximum(10000)
        self.ui.RangeManEnd.setValue(_end)
        self.ui.RangeManEnd.setButtonSymbols(QtWidgets.QSpinBox.NoButtons)
        self.ui.RangeManEnd.setFixedWidth(_width)
        self.ui.RangeManEnd.setAlignment(Qt.AlignCenter)
        self.ui.RangeLayout.addWidget(self.ui.RangeManEnd)

        self.ui.RangeManReset = QtWidgets.QPushButton()
        self.ui.RangeManReset.setObjectName('RangeManReset')
        self.ui.RangeManReset.setFixedWidth(23)
        self.ui.RangeManReset.setIcon(qt.to_icon(icons.RESET))
        self.ui.RangeLayout.addWidget(self.ui.RangeManReset)

        self._manual_range_elems = [
            self.ui.RangeManStart,
            self.ui.RangeManLabel,
            self.ui.RangeManEnd,
            self.ui.RangeManReset,
        ]

        self._callback__Range()

    def _callback__Format(self):
        _fmt = self.ui.Format.currentText()
        self.ui.Burnins.setVisible(_fmt in ('mp4', 'mov'))

    def _callback__Range(self):

        _mode = self.ui.Range.currentText()
        for _elem in self._manual_range_elems:
            _elem.setVisible(_mode == 'Manual')
        _LOGGER.debug('CHANGE RANGE %s %s', _mode, self._read_range())

    def _callback__RangeManReset(self):

        _start, _end = dcc.t_range(int)
        _LOGGER.debug('RESET RANGE %d %d', _start, _end)
        self.ui.RangeManStart.setValue(_start)
        self.ui.RangeManEnd.setValue(_end)

    def _read_range(self):
        """Read range based on current ui settings.

        Returns:
            (tuple): start/end frames
        """
        _mode = self.ui.Range.currentText()
        if _mode == 'From timeline':
            return dcc.t_range(int)
        if _mode == 'Manual':
            return self.ui.RangeManStart.value(), self.ui.RangeManEnd.value()
        raise ValueError(_mode)

    def build_ui(self, parent=None, layout=None):
        """Build ui elements.

        Args:
            parent (QWidget): parent widget
            layout (QLayout): parent layout
        """
        self.add_separator_elem()

        self._build_range_elems()
        _vid_fmt = os.environ.get('PINI_VIDEO_FORMAT', 'mp4')
        self.ui.Format = self.add_combobox_elem(
            'Format', items=[_vid_fmt, 'jpg', 'png'])
        self.add_separator_elem()

        self.ui.Force = self.add_checkbox_elem(
            'Force', label='Replace existing without confirmation')
        self.ui.View = self.add_checkbox_elem(
            'View', label='View blast on completion')
        self.ui.Burnins = self.add_checkbox_elem(
            'Burnins', val=True, label='Add burnins on video compile')
        self.ui.DisableSave = self.add_checkbox_elem(
            'DisableSave', val=False, label='Disable save on blast (unsafe)',
            save_policy=qt.SavePolicy.SAVE_IN_SCENE, tooltip=(
                'Disabling save on blast is unsafe as you may get animation '
                'that does not have a scene file approved'))
        self.add_separator_elem()

    def blast(self):
        """Execute blast."""
        raise NotImplementedError
