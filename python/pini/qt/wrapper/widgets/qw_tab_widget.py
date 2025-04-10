"""Tools for adding functionality to QTabWidget."""

from ...q_mgr import QtWidgets
from ... import q_utils
from . import qw_base_widget


class CTabWidget(QtWidgets.QTabWidget, qw_base_widget.CBaseWidget):
    """Wrapper for QTabWidget."""

    __repr__ = qw_base_widget.CBaseWidget.__repr__

    def find_tabs(self, enabled=None):
        """Find tab names.

        Args:
            enabled (bool): filter by enabled status

        Returns:
            (str list): matching tab names
        """
        _tabs = []
        for _idx in range(self.count()):
            if enabled is not None and self.isTabEnabled(_idx) != enabled:
                continue
            _tabs.append(self.tabText(_idx))
        return _tabs

    def current_tab_name(self):
        """Read name of current tab.

        Returns:
            (str): tab name
        """
        return self.currentWidget().objectName()

    def current_tab_text(self):
        """Read text from current tab.

        Returns:
            (str): tab text
        """
        _idx = self.currentIndex()
        return self.tabText(_idx)

    def get_val(self):
        """Get currently selected tab text.

        Returns:
            (str): tab text
        """
        return self.current_tab_text()

    @q_utils.apply_emit
    def select_tab(self, match, emit=None):
        """Select tab by name.

        Args:
            match (str): name to match
            emit (bool): emit current changed signal on select
        """
        for _idx in range(self.count()):

            _text = self.tabText(_idx)
            _widget = self.widget(_idx)
            _name = _widget.objectName()

            if match not in (_text, _name, _widget, _idx):
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
                _signals = self.signalsBlocked()
                self.blockSignals(True)
                self.setTabEnabled(_idx, enabled)
                self.blockSignals(_signals)
                return
        raise RuntimeError(name)

    @q_utils.apply_emit
    def set_val(self, val, emit=None):
        """Select the given tab.

        Args:
            val (str): name of tab to select
            emit (bool): emit signal on change
        """
        self.select_tab(val)
