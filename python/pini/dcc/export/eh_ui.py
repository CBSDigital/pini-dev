"""Tools for managing export handler interfaces."""

import logging

from pini import qt, pipe, dcc, icons
from pini.tools import release
from pini.qt import QtWidgets, QtGui, Qt
from pini.utils import to_nice, to_snake

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
        self._elems = {}

    def _setup_elem(
            self, elem, name, disable_save_settings=False, save_policy=None,
            settings_key=None, tooltip=None, ui_only=False):
        """Setup element in the export handler's ui.

        This will:
         - Apply object name (eg. MyName)
         - Set this element as an attribute of this object (ie. self.MyName)
         - Apply save policy

        Args:
            elem (QWidget): widget to add
            name (str): widget name
            disable_save_settings (bool): apply disable save settings
                to element
            save_policy (SavePolicy): save policy to apply
                (default is save on change)
            settings_key (str): override settings key for element
            tooltip (str): add tooltip to element
            ui_only (bool): element is ui only (ie. do not pass to exec func)
        """
        assert isinstance(elem, qt.CBaseWidget)

        elem.setObjectName(name)
        setattr(self, name, elem)
        if tooltip:
            elem.setToolTip(tooltip)

        # Setup settings
        _save_policy = save_policy or qt.SavePolicy.SAVE_IN_SCENE
        if disable_save_settings:
            release.apply_deprecation('08/04/25', 'Use save_policy')
            _save_policy = qt.SavePolicy.NO_SAVE
        _settings_key = settings_key or _to_settings_key(
            name=name, handler=self)
        elem.set_settings_key(_settings_key)
        assert isinstance(_save_policy, qt.SavePolicy)
        elem.save_policy = _save_policy
        elem.ui_only = ui_only
        elem.load_setting()

        self._elems[name] = elem

    def _add_elem_lyt(
            self, name, elem, label=None, label_w=None, tooltip=None,
            disable_save_settings=False, save_policy=None, settings_key=None,
            stretch=True, add_elems=(), ui_only=False):
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
            ui_only (bool): element is ui only (ie. do not pass to exec func)
        """
        _label = label or to_nice(name).capitalize()
        _LOGGER.debug('ADD ELEM LAYOUT')

        # Build layout + label
        _h_lyt = self.add_hbox_layout(f'{name}Lyt')
        _label_e = self.add_label(
            f'{name}Label', text=_label, tooltip=tooltip, label_w=label_w)
        _h_lyt.addWidget(_label_e)
        _h_lyt.addWidget(elem)
        if stretch:
            _h_lyt.addStretch()

        for _elem in add_elems:
            _h_lyt.addWidget(_elem)

        self._setup_elem(
            elem, disable_save_settings=disable_save_settings, name=name,
            save_policy=save_policy, tooltip=tooltip, settings_key=settings_key,
            ui_only=ui_only)

    def add_check_box(
            self, name, val=True, label=None, tooltip=None, enabled=True,
            save_policy=None, ui_only=False):
        """Add QCheckBox element in this handler's interface.

        Args:
            name (str): element name
            val (bool): element checked state
            label (str): element label
            tooltip (str): apply tooltip
            enabled (bool): apply enabled state
            save_policy (SavePolicy): save policy to apply
                (default is save on change)
            ui_only (bool): element is ui only (ie. do not pass to exec func)

        Returns:
            (QCheckBox): checkbox element
        """
        _label = label or to_nice(name).capitalize()
        _checkbox_e = qt.CCheckBox(_label, self.parent)
        _checkbox_e.setChecked(val)
        if not enabled:
            _checkbox_e.setEnabled(False)
        self.layout.addWidget(_checkbox_e)

        self._setup_elem(
            elem=_checkbox_e, save_policy=save_policy, name=name,
            ui_only=ui_only, tooltip=tooltip)

        return _checkbox_e

    def add_combo_box(
            self, name, items, data=None, val=None, width=None, label=None,
            label_w=None, tooltip=None, disable_save_settings=False,
            save_policy=None, settings_key=None, ui_only=False):
        """Add a combo box element.

        Args:
            name (str): element name
            items (str list): combo box items
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
            ui_only (bool): element is ui only (ie. do not pass to exec func)

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
            label_w=label_w, save_policy=save_policy, ui_only=ui_only,
            disable_save_settings=disable_save_settings,
            settings_key=settings_key)
        if val:
            _LOGGER.debug(' - APPLY VALUE %s', val)
            _combo_box.select_text(val)
        _LOGGER.debug(' - COMPLETED ADD COMBOBOX %s', _combo_box)

        return _combo_box

    def add_hbox_layout(self, name):
        """Add QHBboxLayout to this interace.

        Args:
            name (str): name for layout

        Returns:
            (QHBoxLayout): layout
        """
        assert name.endswith('Lyt')
        _lyt = QtWidgets.QHBoxLayout(self.parent)
        _lyt.setObjectName(name)
        _lyt.setSpacing(2)
        setattr(self, name, _lyt)
        _LOGGER.debug(' - ADDED LAYOUT %s %s', name, _lyt)
        self.layout.addLayout(_lyt)
        return _lyt

    def add_label(self, name, text=None, label_w=None, tooltip=None):
        """Add QLabel to this inteface.

        Args:
            name (str): name for label element
            text (str): display text for label
            label_w (int): override label width
            tooltip (str): apply label tooltip

        Returns:
            (QLabel): label
        """
        assert name.endswith('Label')
        _label = QtWidgets.QLabel(self.parent)
        _label.setText(text)
        _label.setObjectName(name)
        _label.setFixedWidth(label_w or self.label_w)
        if tooltip:
            _label.setToolTip(tooltip)
        setattr(self, name, _label)
        _LOGGER.debug(' - ADD LABEL %s %s', name, _label)

        return _label

    def add_icon_button(self, name, icon, callback):
        """Add icon button element.

        Args:
            name (str): element name
            icon (str): path to element icon
            callback (fn): element callback

        Returns:
            (QPushButton): icon button
        """
        _btn = QtWidgets.QPushButton(self.parent)
        _btn.setObjectName(f'{name}Refresh')
        _btn.setIcon(qt.obt_icon(icon))
        _btn.setFixedSize(qt.to_size(20))
        _btn.setIconSize(qt.to_size(20))
        _btn.setFlat(True)
        _btn.clicked.connect(callback)
        setattr(self, name, _btn)
        return _btn

    def add_line_edit(
            self, name, val=None, label=None, tooltip=None,
            save_policy=None, disable_save_settings=False, add_elems=()):
        """Add QLineEdit element to this handler's interface.

        Args:
            name (str): element name
            val (str): text for element
            label (str): element label
            tooltip (str): apply tooltip
            save_policy (SavePolicy): save policy to apply
                (default is save on change)
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
            disable_save_settings=disable_save_settings,
            save_policy=save_policy, stretch=False,
            add_elems=add_elems)

        return _lineedit

    def add_list_widget(
            self, name, items=None, label=None, icon_size=30, redraw=True,
            multi=True):
        """Add CListWidget element to this interface.

        Args:
            name (str): element name
            items (list): list items
            label (str): element label
            icon_size (int): icon size (in pixels)
            redraw (bool): widget on build (this should be disabled if the
                redraw function uses elements which haven't been created yet)
            multi (bool): allow multi selection
        """
        self.add_separator()

        # Build label layout
        _label = self.add_label(name=f'{name}Label', text=label or name)
        _lyt = self.add_hbox_layout(f'{name}Lyt')
        _lyt.addWidget(_label)
        _lyt.addStretch()

        # Add refresh button
        _redraw_fn = getattr(self.handler, f'_redraw__{name}', None)
        _LOGGER.debug(' - REFRESH %s %s', f'_redraw__{name}', _redraw_fn)
        if _redraw_fn:
            _btn = self.add_icon_button(
                f'{name}Refresh', icon=icons.REFRESH, callback=_redraw_fn)
            _lyt.addWidget(_btn)

        # Build list
        _list = qt.CListWidget(self.parent)
        if multi:
            _sel_mode = QtWidgets.QListView.ExtendedSelection
        else:
            _sel_mode = QtWidgets.QListView.SingleSelection
        _list.setSelectionMode(_sel_mode)
        _list.setIconSize(qt.to_size(icon_size))
        _list.setSizePolicy(
            QtWidgets.QSizePolicy.Expanding,
            QtWidgets.QSizePolicy.MinimumExpanding)
        self._setup_elem(_list, name=name)
        if items:
            _list.set_items(items, emit=False)
        elif redraw and _redraw_fn:
            _redraw_fn()
        self.layout.addWidget(_list)
        self.layout.setStretch(self.layout.count() - 1, 1)

    def add_exec_button(self, label):
        """Build execute button.

        Args:
            label (str): label for button
        """
        self.add_push_button(
            'Execute', label, callback=self.handler.exec_from_ui)

    def add_push_button(self, name, label=None, callback=None):
        """Add push button element.

        Args:
            name (str): element name
            label (str): element label
            callback (fn): button callback
        """
        _btn = QtWidgets.QPushButton(self.parent)
        _btn.setText(label or name)
        _btn.setObjectName(name)
        setattr(self, name, _btn)
        if callback:
            _btn.clicked.connect(callback)
        self.layout.addWidget(_btn)

    def add_separator(self, name=None):
        """Add a separator to the ui.

        Args:
            name (str): separator name
        """
        _sep = qt.CHLine(self.parent)
        if name:
            _sep.setObjectName(name)
        self.layout.addWidget(_sep)

    def add_spin_box(
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

    def add_footer_elems(
            self, add_snapshot=True, add_version_up=True, add_notes=True,
            version_up=True):
        """Add footer ui elements.

        These appear at the bottom of the export interface.

        Args:
            add_snapshot (bool): add snapshot option
            add_version_up (bool): add version up option
            add_notes (bool): add notes element
            version_up (bool): default version up setting
        """
        if add_snapshot or add_version_up or add_notes:
            self.add_separator()

        if add_snapshot:
            self.Snapshot = self.add_check_box(
                'Snapshot', label='Take snapshot')
            self.snapshot_elem = self.Snapshot
        if add_version_up:
            self.VersionUp = self.add_check_box(
                'VersionUp', label='Version up', val=version_up)
        if add_notes:
            self.add_notes_elem()

    def add_notes_elem(self):
        """Add notes element to the ui."""
        _work = pipe.cur_work()
        _notes = _work.notes if _work else ''
        self.Notes = self.add_line_edit(
            name='Notes', val=_notes, save_policy=qt.SavePolicy.NO_SAVE)
        self.notes_elem = self.Notes

    def add_range_elems(self):
        """Build range elements.

        The allow the range to be manually set.
        """
        _start, _end = dcc.t_range()
        _width = 40

        self.add_combo_box(
            'Range', items=['From timeline', 'Manual', 'Current frame'])
        self.Range.currentIndexChanged.connect(self._callback__Range)

        self.RangeManStart = QtWidgets.QSpinBox()
        self.RangeManStart.setObjectName('RangeManStart')
        self.RangeManStart.setMaximum(10000)
        self.RangeManStart.setValue(_start)
        self.RangeManStart.setButtonSymbols(QtWidgets.QSpinBox.NoButtons)
        self.RangeManStart.setFixedWidth(_width)
        self.RangeManStart.setAlignment(Qt.AlignCenter)
        self.RangeManStart.save_policy = qt.SavePolicy.NO_SAVE
        self.RangeLyt.addWidget(self.RangeManStart)

        _label = self.add_label('RangeLabel')
        self.RangeLyt.addWidget(_label)

        self.RangeManEnd = QtWidgets.QSpinBox()
        self.RangeManEnd.setObjectName('RangeManEnd')
        self.RangeManEnd.setMaximum(10000)
        self.RangeManEnd.setValue(_end)
        self.RangeManEnd.setButtonSymbols(QtWidgets.QSpinBox.NoButtons)
        self.RangeManEnd.setFixedWidth(_width)
        self.RangeManEnd.setAlignment(Qt.AlignCenter)
        self.RangeManEnd.save_policy = qt.SavePolicy.NO_SAVE
        self.RangeLyt.addWidget(self.RangeManEnd)

        _btn = self.add_icon_button(
            'RangeRefresh', icons.REFRESH,
            callback=self._callback__RangeRefresh)
        self.RangeLyt.addWidget(_btn)

        self._callback__Range()

    def to_kwargs(self):
        """Obtain execute kwargs from elements in this interface.

        Returns:
            (dict): kwargs
        """
        _LOGGER.info('TO KWARGS %s', self)
        _kwargs = {}
        for _name, _elem in self._elems.items():
            _LOGGER.info(' - ELEM %s', _elem)
            if _elem.ui_only:
                continue
            _name = to_snake(_name)
            _val = _elem.get_val()
            if _name == 'range':
                _name = 'range_'
                _val = self.handler.to_range()
            elif _name == 'format':
                _name = 'format_'
            elif isinstance(_elem, qt.CListWidget):
                _sel_mode = _elem.selectionMode()
                if _sel_mode == _elem.SelectionMode.SingleSelection:
                    _val = _elem.selected_data()
                else:
                    _val = _elem.selected_datas()
            _kwargs[_name] = _val
        return _kwargs

    def _callback__Range(self):
        _mode = self.Range.currentText()

        for _elem in [self.RangeManStart, self.RangeManEnd]:
            _elem.setVisible(_mode == 'Manual')

        # Apply alignment
        if _mode == 'Manual':
            self.RangeLabel.setFixedWidth(21)
            _align = Qt.AlignHCenter
        else:
            self.RangeLabel.setFixedWidth(100)
            _align = Qt.AlignRight
        self.RangeLabel.setAlignment(_align | Qt.AlignVCenter)

        self._callback__RangeRefresh()

    def _callback__RangeRefresh(self):
        _LOGGER.debug('REFRESH RANGE %s', self)

        _mode = self.Range.currentText()
        _start, _end = dcc.t_range(int)
        _space = ' ' * 3

        if _mode == 'Manual':
            self.RangeLabel.setText('to')
            self.RangeManStart.setValue(_start)
            self.RangeManEnd.setValue(_end)
        elif _mode == 'Current frame':
            _frame = dcc.t_frame(int)
            self.RangeLabel.setText(f'{_frame}{_space}')
        elif _mode == 'From timeline':
            self.RangeLabel.setText(f'{_start:d} - {_end:d}{_space}')
        else:
            raise ValueError(_mode)


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
