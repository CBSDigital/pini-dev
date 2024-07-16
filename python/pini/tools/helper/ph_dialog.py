"""Tools for managing basic standalone PiniHelper interface."""

# pylint: disable=abstract-method

import logging

from pini import qt
from . import ph_base

_LOGGER = logging.getLogger(__name__)


class PiniHelper(qt.CUiDialog, ph_base.BasePiniHelper):
    """Basic standalone Pini Helper dialog."""

    init_ui = ph_base.BasePiniHelper.init_ui
    timerEvent = ph_base.BasePiniHelper.timerEvent

    def __init__(
            self, jump_to=None, admin=None, parent=None,
            load_settings=True, show=True, reset_cache=True, title=None):
        """Constructor.

        Args:
            jump_to (str): path to jump interface to on launch
            admin (bool): launch in admin mode with create entity/task options
            parent (QDialog): parent dialog
            load_settings (bool): load settings on launch
            show (bool): show on launch
            reset_cache (bool): reset pipeline cache on launch
            title (str): override helper window title
        """
        super(PiniHelper, self).__init__(
            ui_file=ph_base.UI_FILE, load_settings=False, show=False,
            parent=parent)
        ph_base.BasePiniHelper.__init__(
            self, jump_to=jump_to, admin=admin, load_settings=load_settings,
            show=show, reset_cache=reset_cache, title=title)

    def closeEvent(self, event=None):
        """Triggered by close.

        Args:
            event (QEvent): close event
        """
        _LOGGER.debug('CLOSE EVENT %s', self.pos())
        super(PiniHelper, self).closeEvent(event)
        _LOGGER.debug(' - CLOSED DIALOG %s', self.pos())
        ph_base.BasePiniHelper.closeEvent(self, event)
        _LOGGER.debug(' - CLOSED BASE %s', self.pos())
