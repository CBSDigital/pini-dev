"""Tools for managing the base CExportHandler class.

An export handler is a plugin to facilitate exporting (eg rendering,
publishing) to pipeline by a dcc.
"""

import logging

from pini import qt, icons, pipe
from pini.qt import QtWidgets
from pini.utils import to_nice, cache_result, str_to_seed, chain_fns

from . import eh_utils

_LOGGER = logging.getLogger(__name__)


class CExportHandler(object):
    """Base class for any export handler."""

    NAME = None
    ACTION = None
    LABEL_WIDTH = 70
    ICON = None

    description = None
    notes_elem = None

    # For building ui
    parent = None
    layout = None

    def __init__(self):
        """Constructor."""
        self.ui = None
        assert self.ACTION
        _name = self.NAME or type(self).__name__
        _name = _name.lower().replace(' ', '_')
        self._settings_file = '{}/{}.ini'.format(qt.SETTINGS_DIR, _name)

    def _add_elem(
            self, name, elem, label=None, label_width=None, tooltip=None,
            disable_save_settings=False, stretch=True):
        """Add a layout containing the given element.

        Args:
            name (str): name base for elements
            elem (QWidget): active element in layout
            label (str): layout label
            label_width (int): override default label width
            tooltip (str): add tooltip to element
            disable_save_settings (bool): apply disable save settings to element
            stretch (bool): apply stretch to element to fill available
                horizontal space
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
        _label_e.setFixedWidth(label_width or self.LABEL_WIDTH)
        setattr(self.ui, _label_name, _label_e)
        _LOGGER.debug(' - SET LABEL %s %s', _label_name, _label_e)

        _h_lyt.addWidget(_label_e)
        _h_lyt.addWidget(elem)
        if stretch:
            _h_lyt.addStretch()
        self.layout.addLayout(_h_lyt)

        # Update element
        elem.setObjectName(name)
        if tooltip:
            elem.setToolTip(tooltip)
            _label_e.setToolTip(tooltip)
        elem.disable_save_settings = disable_save_settings

    def add_combobox_elem(
            self, name, items, val=None, width=None, label=None,
            label_width=None, tooltip=None, disable_save_settings=False):
        """Add a combobox element.

        Args:
            name (str): element name
            items (str list): combobox items
            val (str): item to select
            width (int): override element width
            label (str): element label
            label_width (int): override default label width
            tooltip (str): add tooltip to element
            disable_save_settings (bool): apply disable save settings to element

        Returns:
            (CComboBox): combo box element
        """
        _combo_box = qt.CComboBox(self.parent)
        if width:
            _combo_box.setFixedWidth(width)
        _combo_box.set_items(items)

        self._add_elem(
            name=name, elem=_combo_box, label=label, tooltip=tooltip,
            label_width=label_width,
            disable_save_settings=disable_save_settings)
        if val:
            _combo_box.select_text(val)
        return _combo_box

    def add_checkbox_elem(
            self, name, val=True, label=None,
            tooltip=None, enabled=True):
        """Add QCheckBox element in this handler's interface.

        Args:
            name (str): element name
            val (bool): element checked state
            label (str): element label
            tooltip (str): apply tooltip
            enabled (bool): apply enabled state

        Returns:
            (QCheckBox): checkbox element
        """
        _label = label or to_nice(name).capitalize()
        _checkbox_e = QtWidgets.QCheckBox(_label, self.parent)
        _checkbox_e.setObjectName(name)
        _checkbox_e.setChecked(val)
        if not enabled:
            _checkbox_e.setEnabled(False)
        if tooltip:
            _checkbox_e.setToolTip(tooltip)
        self.layout.addWidget(_checkbox_e)

        return _checkbox_e

    def add_lineedit_elem(
            self, name, val=None, label=None, tooltip=None,
            disable_save_settings=False):
        """Add QLineEdit element to this handler's interface.

        Args:
            name (str): element name
            val (str): text for element
            label (str): element label
            tooltip (str): apply tooltip
            disable_save_settings (bool): apply disable save settings to element

        Returns:
            (QListEdit): line edit element
        """
        _lineedit = qt.CLineEdit(self.parent)
        if val:
            _lineedit.setText(val)
        _lineedit.setSizePolicy(
            QtWidgets.QSizePolicy.MinimumExpanding,
            QtWidgets.QSizePolicy.Fixed)
        self._add_elem(
            name=name, elem=_lineedit, label=label, tooltip=tooltip,
            disable_save_settings=disable_save_settings, stretch=False)
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
            self, name, val, label=None, label_width=None, tooltip=None,
            disable_save_settings=False):
        """Build a QSpinBox element in this handler's interface.

        Args:
            name (str): element name
            val (int): element value
            label (str): element label
            label_width (int): element label width
            tooltip (str): apply tooltip
            disable_save_settings (bool): disable save settings to disk

        Returns:
            (QSpinBox): spinbox element
        """
        _spinbox = QtWidgets.QSpinBox()
        _spinbox.setValue(val)
        _spinbox.setFixedWidth(45)

        self._add_elem(
            name=name, elem=_spinbox, label=label, tooltip=tooltip,
            disable_save_settings=disable_save_settings,
            label_width=label_width)

        return _spinbox

    def add_footer_elems(self):
        """Add footer publish ui elements.

        These appear at the bottom of the publish interface.
        """

        self.ui.Snapshot = self.add_checkbox_elem(
            'Snapshot', label='Take snapshot')
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

    def obtain_metadata(
            self, work=None, sanity_check_=False, task=None, force=False):
        """Obtain metadata to apply to a generated export.

        Args:
            work (CPWork): override workfile to read metadata from
            sanity_check_ (bool): run sanity checks before publish
            task (str): task to pass to sanity check
            force (bool): force completion without any confirmations

        Returns:
            (dict): metadata
        """

        if self.ui and self.ui.is_active() and self.notes_elem:
            _notes = self.notes_elem.text()
        else:
            _notes = None

        _LOGGER.info('NOTES %s', _notes)
        _data = eh_utils.obtain_metadata(
            action=self.ACTION, work=work, sanity_check_=sanity_check_,
            force=force, handler=self.NAME, task=task, notes=_notes)
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
        self.ui = self.ui or qt.CUiContainer(
            settings_file=self._settings_file)

        qt.flush_layout(layout)
        self.build_ui(parent=parent, layout=layout)
        self.ui.load_settings()

        # Connect callbacks + save settings on change vals
        _widgets = qt.find_layout_widgets(layout)
        _LOGGER.debug(' - CONNECTING %d WIDGETS', len(_widgets))
        for _widget in _widgets:
            _name = _widget.objectName()
            _signal = qt.widget_to_signal(_widget)
            if not _signal:
                continue
            _callback = getattr(self, '_callback__'+_name, None)
            _LOGGER.debug('   - CHECKING %s callback=%s', _name, _callback)
            if _callback:
                _func = chain_fns(
                    self.ui.save_settings,
                    _callback)
                _callback()
            else:
                _func = self.ui.save_settings
            _signal.connect(_func)

    def __repr__(self):
        return '<{}>'.format(type(self).__name__.strip('_'))
