"""Tools for adding functionality to QTabWidget."""

from ...q_mgr import QtWidgets


class CTabWidget(QtWidgets.QTabWidget):
    """Wrapper for QTabWidget."""

    def current_tab_text(self):
        """Read text from current tab.

        Returns:
            (str): tab text
        """
        _idx = self.currentIndex()
        return self.tabText(_idx)

    def select_tab(self, match, emit=None):
        """Select tab by name.

        Args:
            match (str): name to match
            emit (bool): emit current changed signal on select
        """
        for _idx in range(self.count()):

            if match != self.tabText(_idx):
                continue

            _signals = self.signalsBlocked()
            self.blockSignals(True)
            _emit = emit
            if self.currentIndex() != _idx:
                self.setCurrentIndex(_idx)
                if emit is None:
                    _emit = True
            self.blockSignals(False)
            if _emit:
                self.currentChanged.emit(_idx)
            return

        raise RuntimeError(match)

    def set_tab_enabled(self, name, enabled=True):
        """Set the enabled state of the named tab.

        Args:
            name (str): name of tab to enable
            enabled (bool): enabled state to apply
        """
        for _idx in range(self.count()):
            if name == self.tabText(_idx):
                self.setTabEnabled(_idx, enabled)
                return
        raise RuntimeError(name)
