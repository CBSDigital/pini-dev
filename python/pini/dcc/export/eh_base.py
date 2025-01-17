"""Tools for managing the base CExportHandler class.

An export handler is a plugin to facilitate exporting (eg rendering,
publishing) to pipeline by a dcc.
"""

# pylint: disable=too-many-instance-attributes

import logging

from pini import qt, icons, pipe
from pini.qt import QtWidgets, QtGui, Qt
from pini.utils import (
    to_nice, cache_result, str_to_seed, wrap_fn, last, single)

from . import eh_utils

_LOGGER = logging.getLogger(__name__)


class CExportHandler:
    """Base class for any export handler."""

    NAME = None
    TYPE = None
    ACTION = None
    ICON = None

    description = None

    notes_elem = None
    snapshot_elem = None

    # For building ui
    parent = None
    layout = None

    def __init__(self, priority=50, label_w=70):
        """Constructor.

        Args:
            priority (int): sort priority (higher priority handlers
                are sorted to top of option lists)
            label_w (int): label width in ui
        """
        self.ui = None
        self.priority = priority
        self.label_w = label_w
        assert self.ACTION
        _name = self.NAME or type(self).__name__
        _name = _name.lower().replace(' ', '_')
        self._settings_file = f'{qt.SETTINGS_DIR}/{_name}.ini'

    def _add_elem(
            self, elem, name, disable_save_settings=False, save_policy=None,
            settings_key=None, tooltip=None):
        """Setup element in the export handler's ui.

        Args:
            elem (QWidget): widget to add
            name (str): widget name
            disable_save_settings (bool): apply disable save settings to element
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

        # Connect signals
        _signal = qt.widget_to_signal(elem)
        _callback = getattr(self, '_callback__'+name, None)
        if _callback:
            _signal.connect(_callback)
        _apply_save_policy = wrap_fn(
            elem.apply_save_policy_on_change, self.ui.settings)
        _signal.connect(_apply_save_policy)

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
        _h_lyt_name = name+'Layout'
        _h_lyt = QtWidgets.QHBoxLayout(self.parent)
        _h_lyt.setObjectName(_h_lyt_name)
        _h_lyt.setSpacing(2)
        setattr(self.ui, _h_lyt_name, _h_lyt)
        _LOGGER.debug(' - SET LAYOUT %s %s', _h_lyt_name, _h_lyt)

        # Add label
        _label_name = name+'Label'
        _label_e = QtWidgets.QLabel(self.parent)
        _label_e.setText(_label)
        _label_e.setObjectName(_label_name)
        _label_e.setFixedWidth(label_w or self.label_w)
        if tooltip:
            _label_e.setToolTip(tooltip)
        setattr(self.ui, _label_name, _label_e)
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
            self.ui.Snapshot = self.add_checkbox_elem(
                'Snapshot', label='Take snapshot')
            self.snapshot_elem = self.ui.Snapshot
        self.ui.VersionUp = self.add_checkbox_elem(
            'VersionUp', label='Version up')
        self.add_notes_elem()

    def add_notes_elem(self):
        """Add notes element to the ui."""
        _work = pipe.cur_work()
        _notes = _work.notes if _work else ''
        self.ui.Notes = self.add_lineedit_elem(
            name='Notes', val=_notes, disable_save_settings=True)
        self.notes_elem = self.ui.Notes

    def build_ui(self, parent=None, layout=None):
        """Build any specific ui elements for this handler.

        The elements should be added to the given layout.

        This should be implemeneted in the child class.

        Args:
            parent (QWidget): parent widget
            layout (QLayout): layout to add elements to
        """
        _LOGGER.debug('BUILD UI %s %s', parent, layout)

    def build_metadata(
            self, work=None, sanity_check_=True, task=None, force=False):
        """Obtain metadata to apply to a generated export.

        Args:
            work (CPWork): override workfile to read metadata from
            sanity_check_ (bool): run sanity checks before publish
            task (str): task to pass to sanity check
            force (bool): force completion without any confirmations

        Returns:
            (dict): metadata
        """

        # Handle notes
        if self.ui and self.ui.is_active() and self.notes_elem:
            _notes = self.notes_elem.text()
        else:
            _notes = None
        if not force and not _notes:
            _notes = qt.input_dialog(
                'Please enter notes for this export:', title='Notes')
            if self.notes_elem:
                _LOGGER.debug(' - APPLY NOTES %s %s', _notes, self.notes_elem)
                self.notes_elem.setText(_notes)

        _LOGGER.debug('NOTES %s', _notes)
        _data = eh_utils.build_metadata(
            action=self.ACTION, work=work, sanity_check_=sanity_check_,
            force=force, handler=self.NAME, task=task, notes=_notes,
            require_notes=True)

        return _data

    @cache_result
    def to_icon(self):
        """Obtain icon for this export handler.

        Returns:
            (str): path to icon
        """
        if self.ICON:
            return self.ICON
        _rand = str_to_seed(self.NAME)
        return _rand.choice(icons.find_grp('AnimalFaces'))

    def ui_is_active(self):
        """Test whether this export handler's ui is currently active.

        Returns:
            (bool): ui active status
        """
        if not self.ui:
            return False
        try:
            _widgets = self.ui.find_widgets()
        except RuntimeError:
            return False
        if not _widgets:
            return False
        _widget = _widgets[0]
        try:
            _widget.objectName()
        except RuntimeError:
            return False
        return True

    def update_ui(self, parent, layout):
        """Builds the ui into the given layout, flushing any existing widgets.

        This method should not be overloaded - use the build_ui method.

        Args:
            parent (QWidget): parent widget
            layout (QLayout): layout to add elements to
        """
        self.parent = parent
        self.layout = layout

        _LOGGER.debug('UPDATE UI %s', self)
        self.ui = self.ui or qt.CUiContainer(settings_file=self._settings_file)

        qt.flush_layout(layout)
        self.build_ui(parent=parent, layout=layout)
        self.ui.load_settings()

    def post_export(
            self, work, outs=(), version_up=None, update_cache=True,
            notes=None):
        """Execute post export code.

        This manages updating the shot publish cache and cache and can
        also be extended in subclasses.

        Args:
            work (CPWork): source work file
            outs (CPOutput list): outputs that were generated
            version_up (bool): whether to version up on publish
            update_cache (bool): update work file cache
            notes (str): export notes
        """
        _LOGGER.info('POST EXPORT %s', work.path)
        _LOGGER.info(' - OUTS %d %s', len(outs), outs)

        if self.snapshot_elem:
            self._apply_snapshot(work=work)

        if update_cache:
            if pipe.SHOTGRID_AVAILABLE:
                self._register_in_shotgrid(work=work, outs=outs)
            self._update_pipe_cache(work=work, outs=outs)

        # Apply notes to work
        _work_c = pipe.CACHE.obt(work)  # May have been rebuilt on update cache
        _notes = notes or single(
            {_out.metadata['notes'] for _out in outs}, catch=True)
        if _notes and not _work_c.notes:
            _work_c.set_notes(_notes)

        self._apply_version_up(version_up=version_up)

    def _register_in_shotgrid(self, work, outs, upstream_files=None):
        """Register outputs in shotgrid.

        Args:
            work (CPWork): source work file
            outs (CPOutput list): outputs that were generated
            upstream_files (list): list of upstream files
        """
        from pini.pipe import shotgrid
        _thumb = work.image if work.image.exists() else None
        for _last, _out in last(outs):
            _LOGGER.info(' - REGISTER %s update_cache=%d', _out, _last)
            shotgrid.create_pub_file_from_output(
                _out, thumb=_thumb, force=True, update_cache=_last,
                upstream_files=upstream_files)

    def _update_pipe_cache(self, work, outs):
        """Update pipeline cache.

        Args:
            work (CPWork): work file being published
            outs (CPOutput list): outputs being exported
        """
        _work_c = pipe.CACHE.obt(work)  # Has been rebuilt
        _work_c.update_outputs()
        _out_paths = [_out.path for _out in _work_c.outputs]
        for _out in outs:
            if _out.path not in _out_paths:
                raise RuntimeError(
                    f'Missing output {_out.path} - {_out_paths})')
        _LOGGER.info(' - UPDATED CACHE')

    def _apply_snapshot(self, work):
        """Apply take snapshot setting.

        Args:
            work (CPWork): work file
        """
        raise NotImplementedError

    def _apply_version_up(self, version_up=None):
        """Apply version up setting.

        Args:
            version_up (bool): force version up setting
        """
        if version_up is not None:
            _version_up = version_up
        elif self.ui:
            _version_up = self.ui.VersionUp.isChecked()
        else:
            _version_up = False
        if _version_up:
            pipe.version_up()

    def __lt__(self, other):
        return -self.priority < -other.priority

    def __repr__(self):
        _name = type(self).__name__.strip('_')
        return f'<{_name}>'


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
