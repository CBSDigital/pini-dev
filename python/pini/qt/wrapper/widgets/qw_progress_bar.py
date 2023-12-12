"""Tools for managing the QProgressBar wrapper."""

from ...q_mgr import QtWidgets, QtGui
from ...q_utils import to_col


class CProgressBar(QtWidgets.QProgressBar):
    """Wrapper for QProgressBar object."""

    def set_col(self, col):
        """Set colour for this progress bar.

        Args:
            col (str): colour to apply
        """
        _col = to_col(col)
        _palette = QtGui.QPalette()
        _brush = QtGui.QBrush(_col)
        for _state in [
                QtGui.QPalette.Active, QtGui.QPalette.Inactive]:
            _palette.setBrush(
                _state, QtGui.QPalette.Highlight, _brush)
        self.setPalette(_palette)
