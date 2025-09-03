"""Tools for managing export handler interfaces.

NOTES:

 - For clarity, the following method prefixes are used:
     - add: create an element in a horizontal layout (eg. add_line_edit)
     - build: create a single element (eg. build_icon_btn)
     - assemble: create a group of elements (eg. assemble_footer_elems)

 - Separators should be added at the start of blocks, not at the end

"""

import logging

from pini import qt, pipe, dcc, icons
from pini.qt import QtWidgets, QtGui, Qt
from pini.utils import to_nice, to_snake, str_to_ints, ints_to_str

_LOGGER = logging.getLogger(__name__)


class CExportHandlerUI(qt.CUiContainer):
    """Represents an interface in an export handler.


    This is designed to be installed into an existing PiniHelper instance.
    """

    notes_elem = None
    snapshot_elem = None

    range_mode = None

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

    def _add_hbox_layout(self, name):
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
        _LOGGER.debug('     - ADDED LAYOUT %s %s', name, _lyt)
        self.layout.addLayout(_lyt)
        return _lyt

    def _setup_elem(
            self, elem, name, val=None, enabled=None, width=None,
            tooltip=None, save_policy=None, callback=None,
            settings_key=None, ui_only=False):
        """Setup element in the export handler's ui.

        This will:
         - Apply object name (eg. MyName)
         - Set this element as an attribute of this object (ie. self.MyName)
         - Apply save policy
         - Apply any linked callback

        Args:
            elem (QWidget): widget to add
            name (str): widget name
            val (any): value to apply to widget
            enabled (bool): apply widget enabled
            width (int): apply widget width
            tooltip (str): add tooltip to element
            save_policy (SavePolicy): save policy to apply
                (default is save on change)
            callback (fn): callback to link to widget
            settings_key (str): override settings key for element
            ui_only (bool): element is ui only (ie. do not pass to exec func)
        """
        _LOGGER.debug('   - SETUP ELEM %s', name)
        assert isinstance(elem, qt.CBaseWidget)

        elem.setObjectName(name)
        setattr(self, name, elem)

        if val is not None:
            _LOGGER.debug('     - APPLY VAL %s', val)
            elem.set_val(val)
        if enabled is not None:
            elem.setEnabled(enabled)
        if width is not None:
            elem.setFixedWidth(width)
        if tooltip:
            elem.setToolTip(tooltip)

        # Setup settings
        _save_policy = save_policy or qt.SavePolicy.SAVE_IN_SCENE
        _settings_key = settings_key or to_settings_key(
            name=name, handler=self.handler)
        elem.set_settings_key(_settings_key)
        _LOGGER.debug('     - APPLY SETTINGS KEY %s %s', elem, _settings_key)
        assert isinstance(_save_policy, qt.SavePolicy)
        elem.save_policy = _save_policy
        elem.ui_only = ui_only
        elem.load_setting()

        _callback = callback
        if not _callback:
            _callback = getattr(self, f'_callback__{name}', None)
        if _callback:
            qt.widget_to_signal(elem).connect(_callback)

        self._elems[name] = elem

    def _setup_elem_lyt(
            self, elem, label=None, label_w=None, tooltip=None,
            stretch=True, add_elems=(), enabled=None):
        """Add a layout containing the given element.

        Args:
            elem (QWidget): active element in layout
            label (str): layout label
            label_w (int): override default label width
            tooltip (str): add tooltip to element
            stretch (bool): apply stretch to element to fill available
                horizontal space
            add_elems (list): widgets to add to this layout
            enabled (bool): apply enabled state
        """
        _name = elem.objectName()
        _LOGGER.debug('     - SETUP ELEM LYT %s %s', _name, elem)

        _h_lyt = self._add_hbox_layout(f'{_name}Lyt')

        # Build label
        _label = label or to_nice(_name).capitalize()
        _label_e = self.build_label(
            f'{_name}Label', text=_label, tooltip=tooltip,
            width=label_w or self.label_w, enabled=enabled)
        _LOGGER.debug('     - LABEL %s %s', _label_e.objectName(), _label_e)
        _h_lyt.addWidget(_label_e)
        _h_lyt.addWidget(elem)

        if stretch:
            _h_lyt.addStretch()
        for _elem in add_elems:
            _h_lyt.addWidget(_elem)

        return _h_lyt

    def build_icon_btn(self, name, icon, callback):
        """Add icon button element.

        Args:
            name (str): element name
            icon (str): path to element icon
            callback (fn): element callback

        Returns:
            (QPushButton): icon button
        """
        _LOGGER.debug(' - BUILD ICON BTN %s', name)

        _btn = QtWidgets.QPushButton(self.parent)
        _btn.setObjectName(name)
        _btn.setIcon(qt.obt_icon(icon))
        _btn.setFixedSize(qt.to_size(20))
        _btn.setIconSize(qt.to_size(20))
        _btn.setFlat(True)
        _btn.clicked.connect(callback)
        setattr(self, name, _btn)
        _LOGGER.debug('   - BUILD ICON BTN COMPLETE %s', name)

        return _btn

    def build_label(
            self, name, text=None, width=None, tooltip=None,
            align=None, enabled=None):
        """Add QLabel to this inteface.

        Args:
            name (str): name for label element
            text (str): display text for label
            width (int): override label width
            tooltip (str): apply label tooltip
            align (AlignmentFlag): text alignment
            enabled (bool): apply enabled state

        Returns:
            (QLabel): label
        """
        assert (
            name.endswith('Label') or
            name.endswith('Spacer') or
            name.endswith('Sep'))

        _label = QtWidgets.QLabel(self.parent)
        _label.setText(text)
        _label.setObjectName(name)
        if align:
            _label.setAlignment(align)
        if tooltip:
            _label.setToolTip(tooltip)
        if enabled is not None:
            _label.setEnabled(enabled)
        setattr(self, name, _label)
        self._elems[name] = _label
        _LOGGER.debug('     - ADD LABEL %s %s', name, _label)

        if width:
            _label.setFixedWidth(width)

        return _label

    def build_line_edit(self, name, **kwargs):
        """Add QLineEdit to the interface.

        Args:
            name (str): name for line edit

        Returns:
            (QLineEdit): line edit
        """
        _line_edit = qt.CLineEdit(self.parent)
        _line_edit.setSizePolicy(
            QtWidgets.QSizePolicy.MinimumExpanding,
            QtWidgets.QSizePolicy.Fixed)
        self._setup_elem(elem=_line_edit, name=name, **kwargs)
        return _line_edit

    def build_push_btn(self, name, callback, label=None, width=80):
        """Add push button element.

        Args:
            name (str): element name
            callback (fn): button callback
            label (str): button label
            width (int): button width

        Returns:
            (QPushButton): button
        """
        _btn = QtWidgets.QPushButton(self.parent)
        _btn.setObjectName(name)
        _label = label or to_nice(name).capitalize()
        _btn.setText(_label)
        _btn.setFixedSize(qt.to_size(width, 20))
        _btn.clicked.connect(callback)
        setattr(self, name, _btn)
        return _btn

    def build_spin_box(self, name, min_=0, max_=10000, **kwargs):
        """Build a QSpinBox element in this interface.

        Args:
            name (str): element name
            min_ (int): element minimum
            max_ (int): element maximum

        Returns:
            (QSpinBox): spinbox element
        """
        _spinbox = qt.CSpinBox(self.parent)
        _spinbox.setMinimum(min_)
        _spinbox.setMaximum(max_)
        _spinbox.setFixedWidth(45)
        _spinbox.setAlignment(Qt.AlignCenter)

        _font = QtGui.QFont()
        _font.setPointSize(7)
        _spinbox.setFont(_font)

        self._setup_elem(name=name, elem=_spinbox, **kwargs)

        return _spinbox

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
        _LOGGER.debug(' - ADD CHECKBOX %s', name)
        _label = label or to_nice(name).capitalize()
        _checkbox_e = qt.CCheckBox(_label, self.parent)
        _checkbox_e.setChecked(val)
        self.layout.addWidget(_checkbox_e)

        self._setup_elem(
            elem=_checkbox_e, save_policy=save_policy, name=name,
            ui_only=ui_only, tooltip=tooltip, enabled=enabled)

        return _checkbox_e

    def add_combo_box(
            self, name, items, data=None, val=None, width=None, label=None,
            label_w=None, tooltip=None, save_policy=None, settings_key=None,
            ui_only=False, add_elems=(), callback=None, stretch=True):
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
            save_policy (SavePolicy): save policy to apply
                (default is save on change)
            settings_key (str): override settings key for element
            ui_only (bool): element is ui only (ie. do not pass to exec func)
            add_elems (list): widgets to add to this layout
            callback (fn): callback to link to widget
            stretch (bool): apply stretch to element to fill available
                horizontal space

        Returns:
            (CComboBox): combo box element
        """
        _LOGGER.debug(' - ADD COMBOBOX %s', name)

        # Build combo box element
        _combo_box = qt.CComboBox(self.parent)
        if width:
            _combo_box.setFixedWidth(width)

        self._setup_elem(
            name=name, elem=_combo_box, tooltip=tooltip,
            save_policy=save_policy, ui_only=ui_only,
            settings_key=settings_key, callback=callback, val=val)

        self._setup_elem_lyt(
            _combo_box, label=label, tooltip=tooltip, stretch=stretch,
            label_w=label_w, add_elems=add_elems)

        # Need to set items after elem set up to apply save policy
        _combo_box.set_items(items, data=data, emit=False)
        _LOGGER.debug(
            '   - COMPLETED ADD COMBOBOX %s %s', _combo_box,
            _combo_box.currentText())

        return _combo_box

    def add_label(
            self, name, text=None, tooltip=None, align=None, enabled=None):
        """Add QLabel layout line to this inteface.

        Args:
            name (str): name for label element
            text (str): display text for label
            tooltip (str): apply label tooltip
            align (AlignmentFlag): text alignment
            enabled (bool): apply enabled state

        Returns:
            (QLabel): label
        """
        assert name.endswith('Label') or name.endswith('Spacer')

        _label = self.build_label(
            name=name, text=text, tooltip=tooltip, enabled=enabled,
            align=align)

        _lyt_name = f'{name}Lyt'
        _lyt = self._add_hbox_layout(_lyt_name)
        _lyt.addWidget(_label)
        _label.setWordWrap(True)

        return _label

    def add_line_edit(
            self, name, val=None, label=None, tooltip=None,
            save_policy=None, add_elems=(), ui_only=False):
        """Add QLineEdit element to this handler's interface.

        Args:
            name (str): element name
            val (str): text for element
            label (str): element label
            tooltip (str): apply tooltip
            save_policy (SavePolicy): save policy to apply
                (default is save on change)
            add_elems (list): widgets to add to this layout
            ui_only (bool): element is ui only (ie. do not pass to exec func)

        Returns:
            (QListEdit): line edit element
        """
        _line_edit = self.build_line_edit(
            name=name, val=val, tooltip=tooltip, save_policy=save_policy,
            ui_only=ui_only)
        self._setup_elem_lyt(
            elem=_line_edit, label=label, tooltip=tooltip, stretch=False,
            add_elems=add_elems)
        return _line_edit

    def add_list_widget(
            self, name, items=None, label=None, icon_size=30, redraw=True,
            multi=True, select=None, add_elems=()):
        """Add CListWidget element to this interface.

        Args:
            name (str): element name
            items (list): list items
            label (str): element label
            icon_size (int): icon size (in pixels)
            redraw (bool): widget on build (this should be disabled if the
                redraw function uses elements which haven't been created yet)
            multi (bool): allow multi selection
            select (list|any): apply selection
            add_elems (tuple): add elements to label layout
        """
        self.add_separator()

        # Build label layout
        _label = self.build_label(name=f'{name}Label', text=label or name)
        _lyt = self._add_hbox_layout(f'{name}Lyt')
        _lyt.addWidget(_label)
        _lyt.addStretch()
        for _elem in add_elems:
            _lyt.addWidget(_elem)

        # Add refresh button
        _redraw_fn = getattr(self.handler, f'_redraw__{name}', None)
        _LOGGER.debug(' - REFRESH %s %s', f'_redraw__{name}', _redraw_fn)
        if _redraw_fn:
            _btn = self.build_icon_btn(
                name=f'{name}Refresh', icon=icons.REFRESH, callback=_redraw_fn)
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
        if select:
            _list.select(select)
        self.layout.addWidget(_list)
        self.layout.setStretch(self.layout.count() - 1, 1)

    def add_exec_btn(self, label):
        """Build execute button.

        Args:
            label (str): label for button
        """
        self.add_push_btn(
            'Execute', label, callback=self.handler.exec_from_ui)

    def add_push_btn(self, name, label=None, callback=None):
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
            tooltip=None, add_elems=(), width=None, save_policy=None,
            stretch=True, ui_only=False):
        """Build a QSpinBox layout in this handler's interface.

        Args:
            name (str): element name
            val (int): element value
            min_ (int): element minimum
            max_ (int): element maximum
            label (str): element label
            label_w (int): element label width
            tooltip (str): apply tooltip
            add_elems (list): widgets to add to this layout
            width (int): apply widget width
            save_policy (SavePolicy): save policy to apply
            stretch (bool): apply stretch to element to fill space
            ui_only (bool): element is ui only (ie. do not pass to exec func)

        Returns:
            (QSpinBox): spinbox element
        """
        _spinbox = self.build_spin_box(
            name=name, val=val, min_=min_, max_=max_, width=width,
            ui_only=ui_only, save_policy=save_policy)

        self._setup_elem_lyt(
            elem=_spinbox, label=label, tooltip=tooltip, stretch=stretch,
            label_w=label_w, add_elems=add_elems)

        return _spinbox

    def add_notes_elem(self):
        """Add notes element to the ui."""
        _LOGGER.debug(' - ADD NOTES')
        _work = pipe.cur_work()
        _notes = _work.notes if _work else ''
        self.Notes = self.add_line_edit(
            name='Notes', val=_notes, save_policy=qt.SavePolicy.NO_SAVE)
        self.notes_elem = self.Notes

    def assemble_footer_elems(
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

    def assemble_range_elems(self, mode='Continuous'):
        """Build range elements.

        The allow the range to be manually set.

        Args:
            mode (str): apply range mode
        """
        _LOGGER.debug(' - ASSEMBLE RANGE ELEMS')
        _start, _end = dcc.t_range()
        _width = 40
        _mode = {True: 'Continuous', None: 'Continuous'}.get(mode, mode)
        assert _mode in ['Continuous', 'Frames']
        self.range_mode = _mode

        # Set up range mode option
        if _mode == 'Continuous':
            _opts = ['From timeline', 'Manual', 'Current frame']
        elif _mode == 'Frames':
            _opts = [
                'From timeline', 'From render globals',
                'Custom', 'Current frame']
        else:
            raise ValueError(_mode)
        _refresh = self.build_icon_btn(
            'RangeRefresh', icons.REFRESH,
            callback=self._callback__RangeRefresh)
        self.add_combo_box('Range', items=_opts, add_elems=[_refresh])

        if _mode == 'Continuous':
            _start_e = self.add_spin_box(
                'RangeManualStart', max_=10000, val=_start, width=_width,
                # save_policy=qt.SavePolicy.NO_SAVE,
                ui_only=True,
                label='Frames', stretch=False)
            _lyt = self.RangeManualStartLyt
            _sep_e = self.build_label('RangeManualSep', width=5)
            _end_e = self.build_spin_box(
                'RangeManualEnd', max_=10000, val=_end, width=_width,
                # save_policy=qt.SavePolicy.NO_SAVE,
                ui_only=True)
            for _elem in [_start_e, _end_e]:
                _elem.setButtonSymbols(QtWidgets.QSpinBox.NoButtons)
            for _elem in [_sep_e, _end_e]:
                _lyt.addWidget(_elem)
            _lyt.addStretch()
        elif _mode == 'Frames':
            self.add_line_edit(
                'RangeCustom', label='Frames', ui_only=True)
            self.add_spin_box(
                'RangeStepSize', 1, label='Step size', min_=1, ui_only=True)

        _LOGGER.debug('   - ADD RangeFramesLabel')
        self.add_label(
            name='RangeFramesLabel', align=Qt.AlignRight,
            text='<frames not set>')

        self._callback__Range()

    def to_frames(self):
        """Get list of frames to export.

        Returns:
            (int list): frames
        """
        _mode = self.Range.currentText()
        _LOGGER.debug('TO FRAMES %s', _mode)
        if self.range_mode == 'Continuous':
            _step = 1
        elif self.range_mode == 'Frames':
            _step = self.RangeStepSize.get_val()
        else:
            raise ValueError(self.range_mode)
        _LOGGER.debug(' - STEP %s', _step)
        _start, _end = dcc.t_range(int)

        if _mode == 'Manual':
            _start = self.RangeManualStart.get_val()
            _end = self.RangeManualEnd.get_val()
            _frames = list(range(_start, _end + 1, 1))
        elif _mode == 'Current frame':
            _frames = [dcc.t_frame(int)]
        elif _mode == 'From timeline':
            _frames = list(range(_start, _end + 1, _step))
        elif _mode == 'From render globals':
            _frames = dcc.t_frames(mode='RenderGlobals')
        elif _mode == 'Custom':
            _frame_s = self.RangeCustom.text()
            _frames = str_to_ints(_frame_s)
        else:
            raise ValueError(_mode)

        return _frames

    def to_kwargs(self):
        """Obtain execute kwargs from elements in this interface.

        Returns:
            (dict): kwargs
        """
        _LOGGER.debug('TO KWARGS %s', self)
        _kwargs = {}
        for _name, _elem in self._elems.items():
            _LOGGER.debug(' - ELEM %s', _elem)
            if isinstance(_elem, QtWidgets.QLabel):
                continue
            if _elem.ui_only:
                continue
            _name = to_snake(_name)
            _val = _elem.get_val()
            if _name == 'range':
                if self.range_mode == 'Continuous':
                    _name = 'range_'
                    _val = self.handler.to_range()
                elif self.range_mode == 'Frames':
                    _name = 'frames'
                    _val = self.handler.to_frames()
                else:
                    raise ValueError(self.range_mode)
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
        _LOGGER.debug('CALLBACK Range')

        for _name, _vis in [

                ('RangeManualStartLabel', _mode == 'Manual'),
                ('RangeManualStart', _mode == 'Manual'),
                ('RangeManualSep', _mode == 'Manual'),
                ('RangeManualEnd', _mode == 'Manual'),

                ('RangeCustom', _mode == 'Custom'),
                ('RangeCustomLabel', _mode == 'Custom'),

                ('RangeStepSizeLabel', _mode == 'From timeline'),
                ('RangeStepSize', _mode == 'From timeline'),
        ]:

            _LOGGER.debug(' - UPDATE %s %s', _name, _vis)
            if _name not in self._elems:
                _LOGGER.debug('   - ELEM NOT FOUND')
                continue
            _elem = self._elems[_name]
            _elem.setVisible(_vis)

        self._callback__RangeRefresh()

    def _callback__RangeRefresh(self):
        _LOGGER.debug('REFRESH RANGE %s', self)

        _frames = self.to_frames()
        _frame_s = ints_to_str(_frames)
        self.RangeFramesLabel.setText(f'frames: {_frame_s}')

    _callback__RangeCustom = _callback__RangeRefresh
    _callback__RangeManualStart = _callback__RangeRefresh
    _callback__RangeManualEnd = _callback__RangeRefresh
    _callback__RangeStepSize = _callback__RangeRefresh


def to_settings_key(handler, name):
    """Build scene settings key based on the given handler/name.

    Args:
        handler (CExportHandler): export handler
        name (str): widget name

    Returns:
        (str): scene settings key (eg. PiniQt.CMayaModelPublish.References)
    """
    _handler = type(handler).__name__
    return f'PiniQt.{_handler}.{name}'
