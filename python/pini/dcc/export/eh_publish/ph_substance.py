"""Tools for managing texture publishing from substance."""

# pylint: disable=unused-argument

import logging

from substance_painter import textureset

from pini import icons, qt, dcc
from pini.qt import QtWidgets
from pini.utils import last

from substance_pini import s_pipe

from . import ph_basic

_LOGGER = logging.getLogger(__name__)


class CSubstanceTexturePublish(ph_basic.CBasicPublish):
    """Manages a substance texture publish."""

    NAME = 'Substance Texture Publish'
    ICON = icons.find('Framed Picture')
    COL = 'Salmon'
    TYPE = 'Publish'

    LABEL = '\n'.join([
        'Saves textures to disk',
    ])

    def _add_custom_ui_elems(self):
        """Add custom ui elements."""

        _view_outputs = self.ui.build_push_btn(
            name='Preview Outputs', callback=self._raise_outputs_dialog,
            width=70)

        _tex_sets = []
        if dcc.cur_file():
            _tex_sets += textureset.all_texture_sets()

        # Add texture sets
        _emoji = qt.CPixmap(icons.find('Diamond Suit'))
        _sets = []
        for _set in _tex_sets:
            _icon = qt.CPixmap(30, 30)
            _icon.fill('Transparent')
            _icon.draw_overlay(
                _emoji, _icon.center(), size=20, anchor='C')
            _item = qt.CListWidgetItem(
                _set.name, icon=_icon, data=_set.name)
            # _item = qt.CListWidgetItem(_set.name)
            _sets.append(_item)
        self.ui.add_list_widget(
            name='Sets', items=_sets, select=_sets, label='Texture sets',
            add_elems=[_view_outputs])

        self.ui.add_check_box(
            name='Browser', val=False, label='Open texture dir in browser')

    def _raise_outputs_dialog(self):
        """Raise texture outputs dialog."""
        _raise_outputs_dialog(
            sets=self.ui.Sets.selected_texts(),
            parent=self.ui.parent)

    def export(
            self, notes=None, snapshot=True, version_up=True,
            progress=True, browser=False, sets=None,
            sanity_check_=True, force=False):
        """Execute texture publish.

        Args:
            notes (str): publish notes
            snapshot (bool): take snapshot on publish
            version_up (bool): version up on publish
            progress (bool): show publish progress
            browser (bool): open export folder in brower
            sets (str list): export only the given texture sets
            sanity_check_ (bool): apply sanity checks
            force (bool): replace existing without confirmation
        """
        return s_pipe.export_textures(
            work=self.work, browser=browser, force=force, sets=sets,
            progress=self.progress)


class _OutputsDialog(QtWidgets.QDialog):
    """Dialog that displays texture outputs."""

    def __init__(self, data, parent=None):
        """Constructor.

        Args:
            data (dict): texture data to display
            parent (QWidget): parent dialog
        """
        super().__init__(parent)
        self.setWindowTitle("Texture exports")
        self.setMinimumSize(400, 300)
        self.setModal(True)

        # Main layout for the dialog
        _lyt = QtWidgets.QVBoxLayout(self)

        # Create the tree widget
        self.tree_widget = QtWidgets.QTreeWidget()
        self.tree_widget.setHeaderLabels(
            ["Texture", "Filename", 'Res', 'Bit depth'])
        _lyt.addWidget(self.tree_widget)
        self.populate_tree(data)

        # Add a button box with a single "OK" button to close the dialog
        _accept = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok)
        _accept.accepted.connect(self.accept)
        _lyt.addWidget(_accept)

    def populate_tree(self, data):
        """Populate items tree.

        Args:
            data (dict): texture data to display
        """

        # Add items to tree
        for _set, _outputs in data.items():
            _LOGGER.debug(' - ADD SET %s %s', _set, _outputs)
            _set_item = QtWidgets.QTreeWidgetItem(self.tree_widget)
            _set_item.setText(0, _set)
            for _file, _res, _bits in _outputs:
                _item = QtWidgets.QTreeWidgetItem(_set_item)
                _item.setText(1, _file)
                _item.setText(2, _res)
                _item.setText(3, _bits)
        self.tree_widget.expandAll()

        # Adjust column spacing
        for _last, _idx in last(range(4)):
            self.tree_widget.resizeColumnToContents(_idx)
            if not _last:
                _width = self.tree_widget.columnWidth(_idx)
                self.tree_widget.setColumnWidth(_idx, _width + 5)


def _raise_outputs_dialog(sets=None, parent=None):
    """Raise texture outputs dialog.

    Args:
        sets (str list): only display these sets
        parent (QWidget): parent widget
    """

    # Build export data
    _exports = {}
    for _set, _files in s_pipe.to_export_data(sets=sets).items():
        _set_items = []
        for _file_data in _files:
            _res = _file_data['res']
            _bits = _file_data['bits']
            _data = (
                _file_data['filename'],
                f'{_res}x{_res}',
                f'{_bits} bits')
            _set_items.append(_data)
        _exports[_set] = _set_items

    # Raise dialog
    _dlg = _OutputsDialog(
        _exports, parent=parent or dcc.get_main_window_ptr())
    _dlg.resize(qt.to_size(_dlg.width(), 600))
    _dlg.exec_()
