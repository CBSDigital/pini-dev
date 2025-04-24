"""Tools for adding functionality to QTabWidget."""

from ...q_mgr import QtWidgets
from ... import q_utils
from . import qw_base_widget


class CTabWidget(QtWidgets.QTabWidget, qw_base_widget.CBaseWidget):
    """Wrapper for QTabWidget."""

    __repr__ = qw_base_widget.CBaseWidget.__repr__

    def find_tab_idx(self, tab):
        """Find index of the given tab.

        Args:
            tab (int|str|QWidget): tab to match

        Returns:
            (int): index
        """
        for _idx in range(self.count()):
            _tab = self.widget(_idx)
            _text = self.tabText(_idx)
            if tab in [_tab, _text, _idx]:
                return _idx
        raise ValueError(f'Failed to find tab {tab}')

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

    @q_utils.block_signals
    def set_tab_enabled(self, tab, enabled=True):
        """Set the enabled state of the named tab.

        Args:
            tab (str): tab to enable
            enabled (bool): enabled state to apply
        """
        _idx = self.find_tab_idx(tab)
        self.setTabEnabled(_idx, enabled)

    def set_tab_visible(self, tab, visible):
        """Set visiblity of the given tab.

        Args:
            tab (int|str|QWidget): tab to update
            visible (bool): visibility to apply
        """
        _idx = self.find_tab_idx(tab)
        self.setTabVisible(_idx, visible)

    @q_utils.apply_emit
    def set_val(self, val, emit=None):
        """Select the given tab.

        Args:
            val (str): name of tab to select
            emit (bool): emit signal on change
        """
        self.select_tab(val)
