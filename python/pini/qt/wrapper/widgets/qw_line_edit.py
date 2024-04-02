"""Tools for managing the QLineEdit wrapper."""

from ...q_mgr import QtWidgets, QtGui
from . import qw_base_widget


class CLineEdit(QtWidgets.QLineEdit, qw_base_widget.CBaseWidget):
    """Wrapper for QLineEdit."""

    def get_val(self):
        """Read this widget's text.

        Returns:
            (str): text
        """
        return self.text()

    def set_bg_col(self, col):
        """Set background colour for this element.

        Args:
            col (QColor): colour to apply
        """
        _pal = QtGui.QPalette()
        _pal.setColor(QtGui.QPalette.Base, col)
        self.setPalette(_pal)

    def set_text(self, text, emit=True):
        """Set this line edit's text.

        Args:
            text (str): text to apply
            emit (bool): emit signal on apply text
        """
        _blocked = None
        if not emit:
            _blocked = self.signalsBlocked()
            self.blockSignals(True)
        self.setText(text)
        if _blocked is not None:
            self.blockSignals(_blocked)

    def set_val(self, val):
        """Apply text to this widget.

        Args:
            val (str): value to apply
        """
        self.setText(val)
