"""Tools for adding functionality to QSplitter."""

from ...q_mgr import QtWidgets


class CSplitter(QtWidgets.QSplitter):
    """Wrapper for QSplitter.

    NOTE: for some reason applying this in designer seems to make the handle
    width render really wide.
    """

    def set_size(self, size, index=0):
        """Set size of given section.

        The other section is adjusted accordingly.

        Args:
            size (int): size in pixels
            index (int): which section to apply size to (ie. 0 or 1)
        """
        _sizes = self.sizes()
        if index == 0:
            _sizes = size, sum(_sizes) - size
        elif index == 1:
            _sizes = sum(_sizes) - size, size
        else:
            raise ValueError(index)
        self.setSizes(_sizes)
