"""Tools for managing the CUiMainWindow object.

This is a main window with a built in ui loader and some other features
managed, for example connecting callbacks and loading/saving settings.
"""

import logging

from ..q_mgr import QtWidgets
from . import qc_ui_base

_LOGGER = logging.getLogger(__name__)


class CUiMainWindow(QtWidgets.QMainWindow, qc_ui_base.CUiBase):
    """Wrapper for QMainWindow class."""

    keyPressEvent = qc_ui_base.CUiBase.keyPressEvent

    def __init__(
            self, ui_file, ui_loader=None, title=None, fps=None,
            settings_file=None, load_settings=True):
        """Constructor.

        Args:
            ui_file (str): path to ui file
            ui_loader (QUiLoader): override ui loader
            title (str): override window title
            fps (float): start timer at the given frame rate
            settings_file (str): override default settings file path
            load_settings (bool): load settings on launch
        """
        super(CUiMainWindow, self).__init__()  # pylint: disable=no-value-for-parameter
        qc_ui_base.CUiBase.__init__(
            self, ui_file=ui_file, ui_loader=ui_loader, title=title, fps=fps,
            settings_file=settings_file, load_settings=load_settings)

    def closeEvent(self, event=None):
        """Triggered by closing dialog.

        Args:
            event (QCloseEvent): close event
        """
        _LOGGER.info('CLOSE EVENT %s', self)
        qc_ui_base.CUiBase.closeEvent(self, event)
        super(CUiMainWindow, self).closeEvent(event)

    def deleteLater(self):
        """Delete this dialog."""
        _name = str(self)
        _LOGGER.info('DELETE LATER %s', _name)
        super(CUiMainWindow, self).deleteLater()
