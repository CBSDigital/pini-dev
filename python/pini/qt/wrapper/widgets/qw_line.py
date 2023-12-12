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
        super(CHLine, self).__init__(parent)
        self.setFrameShape(self.HLine)
        self.setFrameShadow(self.Sunken)


class CVLine(QtWidgets.QFrame):
    """Vertical line."""

    def __init__(self, parent=None):
        """Constructor.

        Args:
            parent (QWidget): parent widget
        """
        super(CVLine, self).__init__(parent)
        self.setFrameShape(self.VLine)
        self.setFrameShadow(self.Sunken)
