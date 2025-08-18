"""Tools for adding functionality to QCheckBox."""

import logging

from . import qw_base_widget
from ...q_mgr import QtWidgets

_LOGGER = logging.getLogger(__name__)


class CSpinBox(QtWidgets.QSpinBox, qw_base_widget.CBaseWidget):
    """Wrapper for QSpinBox."""

    __repr__ = qw_base_widget.CBaseWidget.__repr__

    def get_val(self):
        """Read value of this element.

        Returns:
            (int): current value
        """
        return self.value()

    def set_val(self, val, catch=True):
        """Set value of this element.

        Args:
            val (int): value to apply
            catch (bool): no error if fail to apply value
        """
        try:
            self.setValue(val)
        except TypeError as _exc:
            if catch:
                return
            raise _exc
