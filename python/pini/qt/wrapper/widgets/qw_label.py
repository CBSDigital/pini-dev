"""Tools for managing the QLabel wrapper."""

import logging

from ...q_mgr import QtWidgets
from . import qw_base_widget

_LOGGER = logging.getLogger(__name__)


class CLabel(QtWidgets.QLabel, qw_base_widget.CBaseWidget):
    """Adds functionality to QLabel object."""

    callback = None

    def set_col(self, col):
        """Set text colour.

        Args:
            col (str): colour to apply
        """
        _pal = self.palette()
        _pal.setColor(self.foregroundRole(), col)
        self.setPalette(_pal)

    def mousePressEvent(self, event):
        """Triggered by mouse press.

        Args:
            event (QMouseEvent): triggered event
        """
        super(CLabel, self).mousePressEvent(event)
        if self.callback:
            self.callback()  # pylint: disable=not-callable
