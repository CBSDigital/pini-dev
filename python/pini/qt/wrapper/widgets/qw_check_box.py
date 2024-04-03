"""Tools for adding functionality to QCheckBox."""

import logging

from . import qw_base_widget
from ...q_mgr import QtWidgets

_LOGGER = logging.getLogger(__name__)


class CCheckBox(QtWidgets.QCheckBox, qw_base_widget.CBaseWidget):
    """Wrapper for QCheckBox."""

    __repr__ = qw_base_widget.CBaseWidget.__repr__

    def get_val(self):
        """Obtain value of this checkbox.

        Returns:
            (bool): checked state
        """
        return self.isChecked()

    def set_val(self, val):
        """Set checkbox checked state.

        Args:
            val (bool): state to apply
        """
        self.setChecked(val)
