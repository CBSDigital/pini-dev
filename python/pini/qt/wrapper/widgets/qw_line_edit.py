"""Tools for managing the QLineEdit wrapper."""

from ...q_mgr import QtWidgets, QtGui


class CLineEdit(QtWidgets.QLineEdit):
    """Wrapper for QLineEdit."""

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
