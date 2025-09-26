"""Tools for managing the CUiMainWindow object.

This is a main window with a built in ui loader and some other features
managed, for example connecting callbacks and loading/saving settings.
"""

import logging

from ..q_mgr import QtWidgets
from . import qc_ui_base

_LOGGER = logging.getLogger(__name__)


class CUiMainWindow(QtWidgets.QMainWindow, qc_ui_base.CUiBaseDummy):
    """Wrapper for QMainWindow class."""

    keyPressEvent = qc_ui_base.CUiBase.keyPressEvent
    __repr__ = qc_ui_base.CUiBaseDummy.__repr__

    def __init__(self, ui_file, parent=None, **kwargs):
        """Constructor.

        Args:
            ui_file (str): path to ui file
            parent (QWidget): parent widget
        """
        from pini import dcc
        _parent = parent or dcc.get_main_window_ptr()
        super().__init__(parent=_parent)
        qc_ui_base.CUiBase.__init__(self, ui_file=ui_file, **kwargs)

    def closeEvent(self, event=None):
        """Triggered by closing dialog.

        Args:
            event (QCloseEvent): close event
        """
        _LOGGER.info('CLOSE EVENT %s', self)
        qc_ui_base.CUiBase.closeEvent(self, event)
        super().closeEvent(event)

    def deleteLater(self):
        """Delete this dialog."""
        _name = str(self)
        _LOGGER.info('DELETE LATER %s', _name)
        super().deleteLater()
