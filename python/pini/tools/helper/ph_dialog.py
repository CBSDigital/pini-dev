"""Tools for managing basic standalone PiniHelper interface."""

# pylint: disable=abstract-method,too-many-ancestors

import logging

from pini import qt
from . import ui

_LOGGER = logging.getLogger(__name__)


class PiniHelper(qt.CUiDialog, ui.PHUiBase):
    """Basic standalone Pini Helper dialog."""

    init_ui = ui.PHUiBase.init_ui
    timerEvent = ui.PHUiBase.timerEvent

    def __init__(
            self, jump_to=None, admin=None, parent=None,
            store_settings=True, show=True, reset_cache=True, title=None):
        """Constructor.

        Args:
            jump_to (str): path to jump interface to on launch
            admin (bool): launch in admin mode with create entity/task options
            parent (QDialog): parent dialog
            store_settings (bool): load settings on launch
            show (bool): show on launch
            reset_cache (bool): reset pipeline cache on launch
            title (str): override helper window title
        """
        super().__init__(
            ui_file=ui.UI_FILE, store_settings=False, show=False,
            parent=parent)
        ui.PHUiBase.__init__(
            self, jump_to=jump_to, admin=admin, store_settings=store_settings,
            show=show, reset_cache=reset_cache, title=title)

    def closeEvent(self, event=None):
        """Triggered by close.

        Args:
            event (QEvent): close event
        """
        _LOGGER.debug('CLOSE EVENT %s', self.pos())
        super().closeEvent(event)
        _LOGGER.debug(' - CLOSED DIALOG %s', self.pos())
        ui.PHUiBase.closeEvent(self, event)
        _LOGGER.debug(' - CLOSED BASE %s', self.pos())
