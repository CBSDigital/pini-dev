"""Tools for managing export handler interfaces."""

import logging

from pini import qt, pipe
from pini.qt import QtWidgets, QtGui, Qt
from pini.utils import to_nice, wrap_fn


_LOGGER = logging.getLogger(__name__)


class CExportHandlerUI(qt.CUiContainer):
    """Represents an interface in an export handler.

    This is designed to be installed into an existing PiniHelper instance.
    """

    notes_elem = None
    snapshot_elem = None

    def __init__(self, settings_file, handler, label_w=70):
        """Constructor.

        Args:
            settings_file (str): path to settings ini file for this handler
            handler (CExportHander): parent export handler
            label_w (int): label width in pixels
        """
        super().__init__(settings_file=settings_file)
        self.handler = handler
        self.label_w = label_w

    def _add_elem(
            self, elem, name, disable_save_settings=False, save_policy=None,
            settings_key=None, tooltip=None):
        """Setup element in the export handler's ui.

        Args:
            elem (QWidget): widget to add
            name (str): widget name
            disable_save_settings (bool): apply disable save settings
                to element
            save_policy (SavePolicy): save policy to apply
                (default is save on change)
            settings_key (str): override settings key for element
            tooltip (str): add tooltip to element
        """
        elem.setObjectName(name)
        if tooltip:
            elem.setToolTip(tooltip)

        # Setup settings
        _save_policy = save_policy or qt.SavePolicy.SAVE_IN_SCENE
        if disable_save_settings:
            _save_policy = qt.SavePolicy.NO_SAVE
        _settings_key = settings_key or _to_settings_key(
            name=name, handler=self)
        elem.set_settings_key(_settings_key)
        assert isinstance(_save_policy, qt.SavePolicy)
        elem.save_policy = _save_policy
        elem.load_setting()
        setattr(self, name, elem)
        self._connect_elem(elem, name)

    def _connect_elem(self, elem, name):
        """Connect element callbacks.

        Args:
            elem (QWidget): element to connect
            name (str): element name
        """
        _signal = qt.widget_to_signal(elem)

        # Connect save on change
        _apply_save_policy = wrap_fn(
            elem.apply_save_policy_on_change, self.settings)
        _signal.connect(_apply_save_policy)

        # Connect callback
        _callback = getattr(self.handler, f'_callback__{name}', None)
        if _callback:
            _signal.connect(_callback)

        # Connect
        _redraw = getattr(self.handler, f'_redraw__{name}', None)
        if _redraw:
            elem.redraw = _redraw
            elem.redraw()

    def _add_elem_lyt(
            self, name, elem, label=None, label_w=None, tooltip=None,
            disable_save_settings=False, save_policy=None, settings_key=None,
            stretch=True, add_elems=()):
        """Add a layout containing the given element.

        Args:
            name (str): name base for elements
            elem (QWidget): active element in layout
            label (str): layout label
            label_w (int): override default label width
            tooltip (str): add tooltip to element
            disable_save_settings (bool): apply disable save settings to element
            save_policy (SavePolicy): save policy to apply
                (default is save on change)
            settings_key (str): override settings key for element
            stretch (bool): apply stretch to element to fill available
                horizontal space
            add_elems (list): widgets to add to this layout
        """
        _label = label or to_nice(name).capitalize()
        _LOGGER.debug('ADD ELEM LAYOUT')

        # Build layout
        _h_lyt_name = name + 'Layout'
        _h_lyt = QtWidgets.QHBoxLayout(self.parent)
        _h_lyt.setObjectName(_h_lyt_name)
        _h_lyt.setSpacing(2)
        setattr(self, _h_lyt_name, _h_lyt)
        _LOGGER.debug(' - SET LAYOUT %s %s', _h_lyt_name, _h_lyt)

        # Add label
        _label_name = name + 'Label'
        _label_e = QtWidgets.QLabel(self.parent)
        _label_e.setText(_label)
        _label_e.setObjectName(_label_name)
        _label_e.setFixedWidth(label_w or self.label_w)
        if tooltip:
            _label_e.setToolTip(tooltip)
        setattr(self, _label_name, _label_e)
        _LOGGER.debug(' - SET LABEL %s %s', _label_name, _label_e)

        _h_lyt.addWidget(_label_e)
        _h_lyt.addWidget(elem)
        if stretch:
            _h_lyt.addStretch()
        self.layout.addLayout(_h_lyt)

        for _elem in add_elems:
            _h_lyt.addWidget(_elem)

        self._add_elem(
            elem, disable_save_settings=disable_save_settings, name=name,
            save_policy=save_policy, tooltip=tooltip,
            settings_key=settings_key)

    def add_checkbox_elem(
            self, name, val=True, label=None, tooltip=None, enabled=True,
            save_policy=None):
        """Add QCheckBox element in this handler's interface.

        Args:
            name (str): element name
            val (bool): element checked state
            label (str): element label
            tooltip (str): apply tooltip
            enabled (bool): apply enabled state
            save_policy (SavePolicy): save policy to apply
                (default is save on change)

        Returns:
            (QCheckBox): checkbox element
        """
        _label = label or to_nice(name).capitalize()
        _checkbox_e = qt.CCheckBox(_label, self.parent)
        _checkbox_e.setChecked(val)
        if not enabled:
            _checkbox_e.setEnabled(False)
        self.layout.addWidget(_checkbox_e)

        self._add_elem(
            elem=_checkbox_e, save_policy=save_policy, name=name,
            tooltip=tooltip)

        return _checkbox_e

    def add_combobox_elem(
            self, name, items, data=None, val=None, width=None, label=None,
            label_w=None, tooltip=None, disable_save_settings=False,
            save_policy=None, settings_key=None):
        """Add a combobox element.

        Args:
            name (str): element name
            items (str list): combobox items
            data (list): list of data corresponding to items
            val (str): item to select
            width (int): override element width
            label (str): element label
            label_w (int): override default label width
            tooltip (str): add tooltip to element
            disable_save_settings (bool): apply disable save settings to element
            save_policy (SavePolicy): save policy to apply
                (default is save on change)
            settings_key (str): override settings key for element

        Returns:
            (CComboBox): combo box element
        """

        # Build combo box element
        _combo_box = qt.CComboBox(self.parent)
        _combo_box.setObjectName(name)
        if width:
            _combo_box.setFixedWidth(width)
        _combo_box.set_items(items, data=data)
        _LOGGER.debug(' - BUILT COMBOBOX %s', _combo_box)

        self._add_elem_lyt(
            name=name, elem=_combo_box, label=label, tooltip=tooltip,
            label_w=label_w, save_policy=save_policy,
            disable_save_settings=disable_save_settings,
            settings_key=settings_key)
        if val:
            _LOGGER.debug(' - APPLY VALUE %s', val)
            _combo_box.select_text(val)
        _LOGGER.debug(' - COMPLETED ADD COMBOBOX %s', _combo_box)

        return _combo_box

    def add_lineedit_elem(
            self, name, val=None, label=None, tooltip=None,
            disable_save_settings=False, add_elems=()):
        """Add QLineEdit element to this handler's interface.

        Args:
            name (str): element name
            val (str): text for element
            label (str): element label
            tooltip (str): apply tooltip
            disable_save_settings (bool): apply disable save settings to element
            add_elems (list): widgets to add to this layout

        Returns:
            (QListEdit): line edit element
        """
        _lineedit = qt.CLineEdit(self.parent)
        if val:
            _lineedit.setText(val)
        _lineedit.setSizePolicy(
            QtWidgets.QSizePolicy.MinimumExpanding,
            QtWidgets.QSizePolicy.Fixed)

        self._add_elem_lyt(
            name=name, elem=_lineedit, label=label, tooltip=tooltip,
            disable_save_settings=disable_save_settings, stretch=False,
            add_elems=add_elems)

        return _lineedit

    def add_separator_elem(self, name=None):
        """Add a separator to the ui.

        Args:
            name (str): separator name
        """
        _sep = qt.CHLine(self.parent)
        if name:
            _sep.setObjectName(name)
        self.layout.addWidget(_sep)

    def add_spinbox_elem(
            self, name, val, min_=0, max_=10000, label=None, label_w=None,
            tooltip=None, disable_save_settings=False):
        """Build a QSpinBox element in this handler's interface.

        Args:
            name (str): element name
            val (int): element value
            min_ (int): element minimum
            max_ (int): element maximum
            label (str): element label
            label_w (int): element label width
            tooltip (str): apply tooltip
            disable_save_settings (bool): disable save settings to disk

        Returns:
            (QSpinBox): spinbox element
        """
        _spinbox = qt.CSpinBox()
        _spinbox.setValue(val)
        _spinbox.setMinimum(min_)
        _spinbox.setMaximum(max_)
        _spinbox.setFixedWidth(45)
        _spinbox.setAlignment(Qt.AlignCenter)

        _font = QtGui.QFont()
        _font.setPointSize(7)
        _spinbox.setFont(_font)

        self._add_elem_lyt(
            name=name, elem=_spinbox, label=label, tooltip=tooltip,
            disable_save_settings=disable_save_settings,
            label_w=label_w)

        return _spinbox

    def add_footer_elems(self, snapshot=True):
        """Add footer ui elements.

        These appear at the bottom of the export interface.

        Args:
            snapshot (bool): add snapshot option
        """
        if snapshot:
            self.Snapshot = self.add_checkbox_elem(
                'Snapshot', label='Take snapshot')
            self.snapshot_elem = self.Snapshot
        self.VersionUp = self.add_checkbox_elem(
            'VersionUp', label='Version up')
        self.add_notes_elem()

    def add_notes_elem(self):
        """Add notes element to the ui."""
        _work = pipe.cur_work()
        _notes = _work.notes if _work else ''
        self.Notes = self.add_lineedit_elem(
            name='Notes', val=_notes, disable_save_settings=True)
        self.notes_elem = self.Notes


def _to_settings_key(handler, name):
    """Build scene settings key based on the given handler/name.

    Args:
        handler (CExportHandler): export handler
        name (str): widget name

    Returns:
        (str): scene settings key (eg. PiniQt.CMayaModelPublish.References)
    """
    _handler = type(handler).__name__
    return f'PiniQt.{_handler}.{name}'
