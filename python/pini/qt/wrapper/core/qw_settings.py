"""Wrapper for QSettings object."""

import logging
import sys

from pini.utils import File, EMPTY, passes_filter

from ...q_mgr import QtCore, QtWidgets

_LOGGER = logging.getLogger(__name__)


class CSettings(QtCore.QSettings, File):
    """Wrapper for QSettings object.

    Settings are managed cumulatively, ie. if you save one setting,
    this won't affect the other settings in the file.
    """

    def __init__(self, file_):
        """Constructor.

        Args:
            file_ (str): path to settings file
        """
        File.__init__(self, file_)
        super(CSettings, self).__init__(self.path, QtCore.QSettings.IniFormat)  # pylint: disable=too-many-function-args

    def apply_to_ui(self, ui, filter_=None):
        """Apply these settings to the given ui object.

        Args:
            ui (CUiContainer): ui to apply settings to
            filter_ (str): filter by widget name
        """
        from pini import qt

        _keys = [_key for _key in self.allKeys()
                 if _key.startswith('widgets/')]
        for _key in _keys:

            # Obtain name/val
            _val = self.value(_key)
            _LOGGER.debug(' - APPLY SETTING %s %s', _key, _val)
            _, _name = _key.split('/')
            if filter_ and not passes_filter(_name, filter_):
                continue

            # Obtain widget
            _widget = ui.find_widget(
                _name, catch=True, case_sensitive=sys.platform != 'win32')
            if not _widget:
                _LOGGER.debug('   - MISSING WIDGET')
                continue

            # Check for disabled
            _save_policy = getattr(
                _widget, 'save_policy', qt.SavePolicy.DEFAULT)
            if _save_policy == qt.SavePolicy.SAVE_IN_SCENE:
                continue
            _disable_save_settings = getattr(
                _widget, 'disable_save_settings', False)
            if _disable_save_settings:
                _LOGGER.debug('   - DISABLED')
                continue

            # Apply
            _LOGGER.debug('   - APPLYING %s %s', _name, _val)
            self.apply_to_widget(widget=_widget, value=_val)

    def apply_to_widget(self, widget, value=EMPTY, emit=True):  # pylint: disable=too-many-branches
        """Apply a setting to a widget.

        If the value is not set, the value is read from the
        widgets section of these settings.

        Args:
            widget (QWidget): widget to apply setting to
            value (any): value to apply
            emit (bool): emit signal on update
        """
        from pini import qt

        _LOGGER.debug(
            'APPLY VALUE %s %s (type=%s)', widget, value, type(value))
        self._check_save_policy(widget)

        # Obtain value
        _val = value
        if _val is EMPTY:
            _key = 'widgets/{}'.format(widget.objectName())
            if _key not in self.allKeys():
                _LOGGER.debug(' - FAILED TO FIND SETTING %s', widget)
                return
            _val = self.value(_key)
            _LOGGER.debug(' - READ VAL %s', _val)

        # Block signals if emit disabled
        _blocked = None
        if not emit:
            _blocked = widget.signalsBlocked()
            widget.blockSignals(True)

        # Apply value
        if isinstance(widget, (QtWidgets.QCheckBox, QtWidgets.QPushButton)):
            _val = {'true': True,
                    'false': False,
                    None: False}.get(_val, _val)
            widget.setChecked(_val)

        elif isinstance(widget, qt.CComboBox):
            widget.select_text(_val)
        elif isinstance(widget, QtWidgets.QComboBox):
            widget.setCurrentText(_val)

        elif isinstance(widget, QtWidgets.QLineEdit):
            widget.setText(_val)
        elif isinstance(widget, QtWidgets.QSlider):
            _val = int(_val or 0)
            widget.setValue(_val)
        elif isinstance(widget, QtWidgets.QSpinBox):
            _val = int(_val or 0)
            widget.setValue(_val)
        elif isinstance(widget, QtWidgets.QSplitter):
            _width = widget.width()
            _val = float(_val or 0.0)
            _sizes = _val*_width, _width-_val*_width
            widget.setSizes(_sizes)
        elif isinstance(widget, QtWidgets.QTabWidget):
            _val = {None: 0}.get(_val, _val)
            _val = int(_val)
            widget.setCurrentIndex(_val)
        elif isinstance(widget, QtWidgets.QTextEdit):
            widget.setPlainText(_val)
        else:
            _LOGGER.info('FAILED TO APPLY SETTING %s %s', widget, _val)

        if _blocked is not None:
            widget.blockSignals(_blocked)

    def _check_save_policy(self, widget):
        """Make sure this widget's save policy is correct.

        Args:
            widget (QWidget): widget being updated
        """
        from pini import testing, qt

        # Check for deprecated disable save settings
        if (
                testing.dev_mode() and
                getattr(widget, 'disable_save_settings', False)):
            raise DeprecationWarning(widget)

        # Make sure save policy is default or save on change
        _save_policy = getattr(widget, 'save_policy', qt.SavePolicy.DEFAULT)
        if _save_policy not in (
                qt.SavePolicy.DEFAULT, qt.SavePolicy.SAVE_ON_CHANGE):
            _LOGGER.info(' - SAVE POLICY %s %s', widget, _save_policy)
            raise RuntimeError(widget)

    def save_ui(self, ui, filter_=None):
        """Save widgets in the given ui to this settings file.

        Args:
            ui (CUiContainer): ui to read widgets from
            filter_ (str): apply string filter
        """
        _widgets = ui.find_widgets(filter_=filter_)
        _LOGGER.debug('SAVE UI %s - FOUND %d WIDGETS', ui, len(_widgets))
        for _widget in _widgets:
            self.save_widget(_widget)

    def save_widget(self, widget):  # pylint: disable=too-many-branches
        """Save the given widget settings.

        Args:
            widget (QWidget): widget to save
        """
        _LOGGER.debug('SAVE WIDGET %s', widget)

        # Check for disabled
        if (
                hasattr(widget, 'disable_save_settings') and
                widget.disable_save_settings):
            _LOGGER.debug(' - DISABLED')
            return

        # Aquire name to build settings key
        try:
            _name = widget.objectName()
        except RuntimeError:
            _LOGGER.debug(' - ERRORED ON GET NAME %s', widget)
            return
        if not _name:
            _LOGGER.debug(' - NO NAME')
            return
        _key = 'widgets/'+_name

        # Read current widget value
        _LOGGER.debug(' - CHECKING %s', _name)
        if isinstance(widget, (QtWidgets.QCheckBox, QtWidgets.QPushButton)):
            _val = widget.isChecked()
        elif isinstance(widget, QtWidgets.QComboBox):
            _val = widget.currentText()
        elif isinstance(widget, QtWidgets.QLineEdit):
            _val = widget.text()
        elif isinstance(widget, QtWidgets.QSlider):
            _val = widget.value()
        elif isinstance(widget, QtWidgets.QSpinBox):
            _val = widget.value()
        elif isinstance(widget, QtWidgets.QSplitter):
            _sizes = widget.sizes()
            if not sum(_sizes):
                return
            _val = 1.0*_sizes[0]/sum(_sizes)
        elif isinstance(widget, QtWidgets.QTabWidget):
            _val = widget.currentIndex()
        elif isinstance(widget, QtWidgets.QTextEdit):
            _val = widget.toPlainText()
        else:
            _LOGGER.debug(' - SAVE NOT IMPLEMENTED %s', _name)
            return

        # Apply to settings
        self.setValue(_key, _val)
        _LOGGER.debug(' - SAVED %s %s', _key, _val)
