"""Tools for managing the CUiDialog object.

This is a dialog with a built in ui loader and some other features
managed, for example connecting callbacks and loading/saving
settings.
"""

import logging

from . import qc_ui_base
from ..q_mgr import QtWidgets

_LOGGER = logging.getLogger(__name__)


class CUiDialog(QtWidgets.QDialog, qc_ui_base.CUiBaseDummy):
    """Base class for any managed ui dialog."""

    keyPressEvent = qc_ui_base.CUiBase.keyPressEvent

    def __init__(
            self, ui_file, parent=None, **kwargs):
        """Constructor.

        Args:
            ui_file (str): path to ui file
            parent (QDialog): parent dialog
            stack_key (str): stack key (default is ui path)
                closes any previous instance of the dialog
                before launching a new one
            load_settings (bool): load settings on launch
            show (bool): show interface on launch
            catch_errors (bool): decorate callbacks with error catcher
            modal (bool): execute dialog modally
        """
        from pini import dcc

        _LOGGER.debug('INIT')
        _parent = parent or dcc.get_main_window_ptr()
        super().__init__(_parent)  # pylint: disable=too-many-function-args
        qc_ui_base.CUiBase.__init__(self, ui_file, **kwargs)

    def closeEvent(self, event=None):
        """Triggered by closing dialog.

        Args:
            event (QCloseEvent): close event
        """
        super().closeEvent(event)
        qc_ui_base.CUiBase.closeEvent(self, event)

    def timerEvent(self, event=None):
        """Triggered by timer.

        Args:
            event (QTimerEvent): triggered event
        """
        super().timerEvent(event)
        qc_ui_base.CUiBase.timerEvent(self, event)
