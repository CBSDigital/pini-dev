"""Tools for managing pyui interfaces built using qt."""

# pylint: disable=unexpected-keyword-arg,no-value-for-parameter

import logging
import sys

from pini import icons, qt, dcc
from pini.qt import QtWidgets, QtGui, Qt
from pini.utils import wrap_fn, File

from . import pu_base, pu_utils
from .. import cpnt

if not hasattr(sys, 'PYUI_QT_INTERFACES'):
    sys.PYUI_QT_INTERFACES = {}

_LOGGER = logging.getLogger(__name__)


class PUQtUi(QtWidgets.QMainWindow, pu_base.PUBaseUi):
    """Qt interface built from a python file."""

    def __init__(self, py_file, **kwargs):
        """Constructor.

        Args:
            py_file (str): path to py file
        """

        # Maintain single instance
        _file = File(py_file)
        if _file.path in sys.PYUI_QT_INTERFACES:
            try:
                sys.PYUI_QT_INTERFACES[_file.path].delete()
            except RuntimeError:
                pass
        sys.PYUI_QT_INTERFACES[_file.path] = self

        self.sections = {}
        self.def_btns = {}
        self.main_layout = None
        self.main_widget = None

        super().__init__(parent=dcc.get_main_window_ptr())
        pu_base.PUBaseUi.__init__(self, py_file, **kwargs)
        self.startTimer(60)

        self.resize(300, 64)
        self.show()

    def init_ui(self):
        """Inititiate interface window."""
        super().init_ui()

        self.setWindowTitle(self.title)

        self.main_widget = QtWidgets.QWidget()
        self.setCentralWidget(self.main_widget)

        self.main_layout = QtWidgets.QVBoxLayout()
        self.main_layout.setSpacing(3)
        self.main_widget.setLayout(self.main_layout)

    def add_menu(self, name):
        """Add menu bar to the interface.

        Args:
            name (str): menu name

        Returns:
            (QMenu): menu
        """
        _menu = qt.CMenu(name)
        self.menuBar().addMenu(_menu)
        _LOGGER.debug(' - ADDED MENU %s %s', name, _menu)
        return _menu

    def add_menu_item(self, parent, label, command=None, image=None):
        """Add menu item to the given menu.

        Args:
            parent (str): menu to add item to
            label (str): item label
            command (fn): item callback
            image (str): path to item image
        """
        _LOGGER.debug('ADD MENU ITEM %s %s', parent, label)
        _args = [label]
        if command:
            _args += [command]
        _action = parent.addAction(*_args)

        if image:
            _icon = qt.to_icon(image)
            _action.setIcon(_icon)

    def add_menu_separator(self, parent):
        """Add a separator item to the given menu bar.

        Args:
            parent (str): menu to add item to
        """
        parent.add_separator()

    def add_separator(self):
        """Add separator item to the interface."""
        _line = QtWidgets.QFrame(self.main_widget)
        _line.setFrameShape(_line.HLine)
        _line.setFrameShadow(_line.Sunken)

        self.main_layout.addWidget(_line)
        self.main_layout.setAlignment(_line, Qt.AlignTop)

        if self._cur_section:
            self._cur_section.add_widgets(_line)

    def init_def(self, def_):
        """Initiate new function.

        Args:
            def_ (PUDef): function to initiate
        """

    def add_arg(self, arg):
        """Add argument.

        Args:
            arg (PUArg): arg to add
        """
        _widgets = []

        # Layout
        _h_layout = QtWidgets.QHBoxLayout(self)
        _h_layout.addStretch(1)
        _h_layout.setSpacing(3)
        self.main_layout.addLayout(_h_layout)

        # Label
        _label = QtWidgets.QLabel(arg.label)
        _label_w = arg.label_w or self.label_w
        _label.resize(_label_w, 13)
        _label.setMinimumSize(_label.size())
        _label.setMaximumSize(_label.size())
        _policy = _label.sizePolicy()
        _policy.setHorizontalPolicy(QtWidgets.QSizePolicy.Fixed)
        _label.setSizePolicy(_policy)
        _h_layout.addWidget(_label)
        _widgets.append(_label)

        # Build field
        _field, _read_fn, _set_fn = self._add_arg_field(arg)
        _h_layout.addWidget(_field)
        _widgets.append(_field)

        if arg.clear:
            _btn = QtWidgets.QPushButton(self)
            _btn.setFixedSize(self.arg_h, self.arg_h)
            _btn.setIcon(qt.to_icon(icons.CLEAR))
            _btn.clicked.connect(wrap_fn(_set_fn, ''))
            _h_layout.addWidget(_btn)
            _widgets.append(_btn)

        if arg.browser:
            _btn = QtWidgets.QPushButton(self)
            _btn.setFixedSize(self.arg_h, self.arg_h)
            _btn.setIcon(qt.to_icon(icons.BROWSER))
            _btn.clicked.connect(wrap_fn(
                pu_utils.apply_browser_btn, mode=arg.browser_mode,
                read_fn=_read_fn, set_fn=_set_fn))
            _h_layout.addWidget(_btn)
            _widgets.append(_btn)

        if self._cur_section:
            self._cur_section.add_widgets(*_widgets)

        return _read_fn, _set_fn, _field

    def _add_arg_field(self, arg):
        """Build an arg field.

        Args:
            arg (PUArg): arg to add

        Returns:
            (tuple): read func, set func, field name
        """
        if arg.choices:
            _field = qt.CComboBox()
            _field.set_items(
                [str(_choice) for _choice in arg.choices],
                data=arg.choices, select=arg.default)
            _read_fn = _field.selected_data
            _set_fn = _to_lazy_combobox_select(_field)
        elif isinstance(arg.default, str) or arg.default is None:
            _field = QtWidgets.QLineEdit()
            if arg.default:
                _field.setText(arg.default)
            _read_fn = _field.text
            _set_fn = _field.setText
        elif isinstance(arg.default, bool):
            _field = QtWidgets.QCheckBox()
            _field.setChecked(arg.default)
            _field.setMinimumHeight(self.arg_h)
            _read_fn = _field.isChecked
            _set_fn = _field.setChecked
        elif isinstance(arg.default, int):
            _field = QtWidgets.QSpinBox()
            _field.setMinimum(-2000000000)
            _field.setMaximum(2000000000)
            _field.setValue(arg.default)
            _read_fn = _field.value
            _set_fn = _field.setValue
        elif isinstance(arg.default, float):
            _field = QtWidgets.QDoubleSpinBox()
            _field.setMinimum(-2000000000)
            _field.setMaximum(2000000000)
            _field.setValue(arg.default)
            _read_fn = _field.value
            _set_fn = _field.setValue
        else:
            raise ValueError(arg.default)

        _field.resize(1000, 13)
        _policy = _field.sizePolicy()
        _policy.setHorizontalPolicy(QtWidgets.QSizePolicy.Expanding)
        _policy.setHorizontalStretch(100)
        _field.setSizePolicy(_policy)

        return _field, _read_fn, _set_fn

    def finalize_def(self, def_):
        """Finalize function.

        Args:
            def_ (PUDef): function to finalize
        """
        _col = qt.to_col(def_.col or self.base_col)
        # _col = QtGui.QColor(_col)

        _h_layout = QtWidgets.QHBoxLayout(self)
        _h_layout.addStretch(1)
        _h_layout.setSpacing(3)
        self.main_layout.addLayout(_h_layout)

        # Code button
        _code = qt.CLabel()
        _code.mousePressEvent = def_.edit
        _code.resize(self.def_h, self.def_h)
        _code.move(3, 23)
        _pix = qt.CPixmap(def_.icon)
        _code.setPixmap(_pix.resize(self.def_h))
        _h_layout.addWidget(_code)

        # Button
        _btn = QtWidgets.QPushButton(def_.label)
        self.def_btns[def_.label] = _btn
        _btn.setObjectName(def_.label)
        _exec = wrap_fn(self._execute_def, def_)
        _exec = _disable_btn_on_exec(_exec, btn=_btn, col=_col)
        _btn.mousePressEvent = _exec
        _set_btn_col(btn=_btn, col=_col)
        _policy = _btn.sizePolicy()
        _policy.setHorizontalPolicy(QtWidgets.QSizePolicy.Expanding)
        _policy.setVerticalPolicy(QtWidgets.QSizePolicy.Expanding)
        _policy.setHorizontalStretch(100)
        _btn.setSizePolicy(_policy)
        # _pal = _btn.palette()
        # _pal.setColor(_pal.Button, _col)
        # _text_col = QtGui.QColor('black' if _col.valueF() > 0.55 else 'white')
        # _pal.setColor(_pal.ButtonText, _text_col)
        # _btn.setAutoFillBackground(True)
        # _btn.setPalette(_pal)
        _h_layout.addWidget(_btn)

        # Info button
        _info = qt.CLabel(self)
        _info.resize(self.def_h, self.def_h)
        _info.move(0, 20)
        _pix = qt.CPixmap(icons.find('Info'))
        _info.setPixmap(_pix.resize(self.def_h))
        _h_layout.addWidget(_info)

        _widgets = [_code, _btn, _info]

        if self._cur_section:
            self._cur_section.add_widgets(*_widgets)

    def set_section(self, section):
        """Set current collapsable section.

        Args:
            section (PUSection): section to apply
        """
        assert isinstance(section, cpnt.PUSection)
        super().set_section(section)

        _section = _PUQtSection(
            section.name, col=self.section_col, collapse=section.collapse,
            parent=self, height=self.sect_h)
        _section.setMinimumSize(100, 22)
        _policy = _section.sizePolicy()
        _policy.setHorizontalPolicy(_policy.Expanding)
        _policy.setHorizontalStretch(100)
        _section.setSizePolicy(_policy)
        self.main_layout.addWidget(_section)
        self.sections[section.name] = _section

        self.callbacks['sections'][section.name] = {
            'get': wrap_fn(getattr, _section, 'collapse'),
            'set': _section.set_collapse}
        self._cur_section = _section

    def collapse_all(self):
        """Collapse all sections."""
        for _section in self.sections.values():
            _section.set_collapse(True)

    def finalize_ui(self):
        """Finalize building interface."""
        self.main_layout.addStretch(1)
        self.resize(300, 64)
        self.show()

    def _apply_section_collapse_update(self):
        """Apply a section collapse status update.

        The ui needs to resize to accommodate the added/removed elements.
        Just adding this to the collapse callback doesn't seem to work,
        so this function is called from within the timer event.
        """
        _LOGGER.debug('TOGGLE SECTION COLLAPSE %s', self)
        _size = qt.to_size(self.width(), 0)
        _LOGGER.debug(' - SIZE %s', _size)
        self.resize(_size)

    def delete(self):
        """Delete this interface."""
        _LOGGER.debug('DELETE')
        self.save_settings()
        self.deleteLater()

    def load_settings(self, settings=None):
        """Load settings from disk.

        Args:
            settings (dict): override settings dict

        Returns:
            (dict): settings that were applied
        """
        _data = super().load_settings(settings=settings)
        _LOGGER.info('LOAD SETTINGS %s', _data.get('geometry'))

        # Apply geom
        _geom = _data.get('geometry')
        if _geom:
            self.setFixedWidth(_geom['width'])
            _pos = _geom['x'], _geom['y']
            self.move(*_pos)
            _LOGGER.info(
                ' - UPDATE POS (%d, %d) / (%d, %d)', _pos[0], _pos[1],
                self.pos().x(), self.pos().y())

        return _data

    def read_settings(self):
        """Read ui settings.

        Returns:
            (dict): ui settings
        """
        _data = super().read_settings()
        _data['geometry'] = {
            'x': self.pos().x(),
            'y': self.pos().y(),
            'width': self.width(),
        }
        _LOGGER.debug(' - READ SETTINGS y=%d', _data['geometry']['y'])
        return _data

    @qt.safe_timer_event
    def timerEvent(self, event):  # pylint: disable=unused-argument
        """Triggered by timer.

        Args:
            event (QTimerEvent): triggered event
        """
        _LOGGER.debug('TIMER')
        self._apply_section_collapse_update()

    def close(self):
        """Close this interface."""
        self.delete()


class _PUQtSection(qt.CPixmapLabel):
    """Header for a collapsible section of defs.

    This mimics to formLayout element in maya - it has a triangle which
    points down when the section is unfolded (not collapse) and points
    to right when the section is folded (collapse). It also had a label
    for the section which appears to the right of the triangle.
    """

    def __init__(self, text, col, parent, height, collapse=False):
        """Constructor.

        Args:
            text (str): section name
            col (QColor): section colour
            parent (QDialog): parent dialog
            height (int): section height
            collapse (bool): collapse state of section
        """
        super().__init__(margin=0)

        self._height = height
        self.text = text
        self.col = col
        self.font = QtGui.QFont()
        self.font.setBold(True)
        self.collapse = collapse
        self.parent = parent

        self.widgets = []

    def add_widgets(self, *widgets):
        """Add widgets to this section."""
        for _widget in widgets:
            self.widgets.append(_widget)
            _widget.setVisible(not self.collapse)

    def redraw_widgets(self):
        """Redraw child widgets."""
        self.redraw()
        for _widget in self.widgets:
            _widget.setVisible(not self.collapse)

    def set_collapse(self, collapse=True):
        """Set collapse state of this section.

        Args:
            collapse (bool): collapse state
        """
        _LOGGER.debug('SET COLLAPSE %d', collapse)
        assert isinstance(collapse, bool)
        self.collapse = collapse
        self.redraw_widgets()
        self.resizeEvent()

    def draw_pixmap(self, pix):
        """Update pixmap.

        Args:
            pix (CPixmap): pixmap to draw on
        """
        pix.fill(self.col)

        _text_col = 'Silver'
        pix.draw_text(
            self.text, pos=(30, self.height()/2), anchor='L',
            col=_text_col, font=self.font)

        _grid = self.height()/3
        if self.collapse:
            _pts = [(_grid*1.5, _grid*0.5),
                    (_grid*2.5, _grid*1.5),
                    (_grid*1.5, _grid*2.5)]
        else:
            _pts = [(_grid, _grid), (_grid*3, _grid), (_grid*2, _grid*2)]
        pix.draw_polygon(_pts, col=_text_col, outline=None)

    def mousePressEvent(self, event=None):
        """Triggered by mouse press.

        Args:
            event (QMouseEvent): triggered event

        Returns:
            (bool): result
        """
        self.set_collapse(not self.collapse)
        return super().mousePressEvent(event)

    def resizeEvent(self, event=None):
        """Triggered resize event.

        Args:
            event (QResizeEvent): triggered event

        Returns:
            (bool): result
        """
        _LOGGER.debug('RESIZE EVENT %s %s', self, self.parent)
        self.setMinimumSize(1, self._height)
        self.redraw()
        return super().resizeEvent(event)


def _disable_btn_on_exec(func, btn, col):
    """Decorate the given function to disable its button on execute.

    The button is also temporarily whitened to mimic maya's behaviour.

    Args:
        func (fn): function to decorate
        btn (QPushButton): button to disable
        col (CColor): button base colour

    Returns:
        (fn): decorated function
    """

    def _wrapped_fn(*args, **kwargs):

        _whitened = col.whiten(0.25)
        _LOGGER.info("DISABLE BTN ON EXEC %s %s", func, btn)
        _set_btn_col(btn, col=_whitened)
        btn.setEnabled(False)
        dcc.refresh()

        try:
            func(*args, **kwargs)
        finally:
            btn.setEnabled(True)
            _set_btn_col(btn, col=col)

    return _wrapped_fn


def _set_btn_col(btn, col):
    """Set colour of the given button.

    Args:
        btn (QPushButton): button to update
        col (CColor): colour to apply
    """
    _pal = btn.palette()
    _pal.setColor(_pal.Button, col)

    _text_col = QtGui.QColor('black' if col.valueF() > 0.55 else 'white')
    _pal.setColor(_pal.ButtonText, _text_col)

    btn.setAutoFillBackground(True)
    btn.setPalette(_pal)


def _to_lazy_combobox_select(field):
    """Build a lazy combobox select function.

    This selects an item but won't error if the item is not available.

    Args:
        field (CComboBox): combobox to update

    Returns:
        (fn): lazy selection function
    """
    def _lazy_select(val):
        field.select_data(val, catch=True)
    return _lazy_select
