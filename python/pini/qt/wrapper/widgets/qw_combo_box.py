"""Tools for adding functionality to QComboBox."""

import logging

from . import qw_base_widget
from ...q_mgr import QtWidgets

_LOGGER = logging.getLogger(__name__)


class CComboBox(QtWidgets.QComboBox, qw_base_widget.CBaseWidget):
    """Wrapper for QComboBox."""

    __repr__ = qw_base_widget.CBaseWidget.__repr__

    def all_data(self):
        """Get list of all item data.

        Returns:
            (any list): data from all items
        """
        return [self.itemData(_idx) for _idx in range(self.count())]

    def all_text(self):
        """Get a list of all item text.

        Returns:
            (str list): item text list
        """
        return [self.itemText(_idx) for _idx in range(self.count())]

    def select_data(self, data, catch=False):
        """Select item based on its data.

        Args:
            data (any): data to select
            catch (bool): no error on fail to select
        """
        _LOGGER.debug('SELECT DATA %s', data)
        for _idx in range(self.count()):
            _data = self.itemData(_idx)
            _LOGGER.debug(' - TESTING DATA %s', _data)
            if _data == data:
                self.setCurrentIndex(_idx)
                return
        if not catch:
            raise ValueError(data)

    def select_text(self, text, emit=None, catch=True):
        """Select item by text.

        Args:
            text (str): text to select
            emit (bool): emit changed signal on apply this change
            catch (bool): no error if fail to select
        """
        if emit is False:
            raise NotImplementedError

        # Apply value
        _applied_val = False
        for _idx in range(self.count()):
            if self.itemText(_idx) == text:
                self.setCurrentIndex(_idx)
                _applied_val = True
                break

        # Apply catch
        if not _applied_val and not catch:
            raise ValueError('Failed to select {}'.format(text))

        # Apply emit
        if emit and not _applied_val:
            self.currentTextChanged.emit(self.currentText())

    def selected_text(self):
        """Obtain currently selected text.

        (Provided for symmetry)

        Returns:
            (str): selected text
        """
        return self.currentText()

    def selected_data(self, mode='by text'):
        """Get selected item data.

        Selection is ambiguous in an editable combobox since if
        the user types in the field, potentially nothing is selected.
        In this case selection by text should be used - if nothing is
        selected this method will return None.

        Args:
            mode (str): how to determine selection

        Returns:
            (any): selected data
        """
        if mode == 'by item':
            return self.itemData(self.currentIndex())
        if mode == 'by text':
            _text = self.currentText()
            for _idx in range(self.count()):
                if self.itemText(_idx) == _text:
                    return self.itemData(_idx)
            return None
        raise ValueError(mode)

    def set_items(self, labels, data=None, select=None, emit=True):
        """Clear the list and apply the given list of items.

        Args:
            labels (str list): items to apply
            data (any list): data to apply
            select (str): item text to select
            emit (bool): emit changed signal after update
        """
        _LOGGER.debug('SET DATA %s %s', self, labels)
        _blocked = self.signalsBlocked()
        _cur_text = self.currentText()
        self.blockSignals(True)

        # Populate list
        self.clear()
        for _idx, _label in enumerate(labels):
            self.addItem(_label)
            if data:
                self.setItemData(_idx, data[_idx])

        # Apply selection
        _LOGGER.debug('APPLY SELECTION %s', select)
        if select and select in labels:
            self.select_text(select)
        elif select and data and select in data:
            self.select_data(select)
        elif _cur_text in labels:
            self.select_text(_cur_text)

        self.blockSignals(_blocked)
        if not _blocked and emit:
            self.currentTextChanged.emit(self.currentText())

    def to_value(self):
        """Obtain value of this combobox's selected text.

        Returns:
            (str): selected text
        """
        return self.currentText()
