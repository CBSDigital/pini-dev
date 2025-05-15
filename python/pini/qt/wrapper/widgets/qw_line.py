"""Tools for managing a designer-like line object.

A designer line is basically a QFrame with some settings applied.
"""

from ...q_mgr import QtWidgets


class CHLine(QtWidgets.QFrame):
    """Horizonal line."""

    def __init__(self, parent=None):
        """Constructor.

        Args:
            parent (QWidget): parent widget
        """
        super().__init__(parent)
        self.setFrameShape(QtWidgets.QFrame.Shape.HLine)
        self.setFrameShadow(QtWidgets.QFrame.Shadow.Sunken)


class CVLine(QtWidgets.QFrame):
    """Vertical line."""

    def __init__(self, parent=None):
        """Constructor.

        Args:
            parent (QWidget): parent widget
        """
        super().__init__(parent)
        self.setFrameShape(self.VLine)
        self.setFrameShadow(self.Sunken)
