"""Tools for managing the QSlider widget wrapper."""

import logging

from pini.utils import val_map

from .qw_base_widget import CBaseWidget
from ...q_mgr import QtWidgets

_LOGGER = logging.getLogger(__name__)


class CSlider(QtWidgets.QSlider, CBaseWidget):
    """Wrapper for QSlider widget."""

    __repr__ = CBaseWidget.__repr__

    def set_fr(self, fraction):
        """Set fractional value.

        Args:
            fraction (float): value to apply
        """
        _val = round(val_map(fraction, out_max=self.maximum()+0.499999))
        _LOGGER.debug('SET FR %s -> %s', fraction, _val)
        self.setValue(_val)

    def to_fr(self):
        """Obtain slider value as a fraction of it maximum value.

        Returns:
            (float): frational value (between 0 and 1)
        """
        return 1.0 * self.value() / self.maximum()
