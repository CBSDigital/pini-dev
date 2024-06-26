"""Tools for managing the multi select dialog."""

import logging

from pini.utils import File

from .. import custom, q_utils

_LOGGER = logging.getLogger(__name__)
_DIR = File(__file__).to_dir()
_UI_FILE = _DIR.to_file('multi_select.ui')


class _MultiSelect(custom.CUiDialog):
    """Modal dialog for selecting items from a list."""

    def __init__(self, msg, title, multi, items, select):
        """Constructor.

        Args:
            msg (str): dialog message
            title (str): dialog title
            multi (bool): allow multiple selections
            items (list): list of items to select from
            select (any|list): item/items to select by default
        """
        self.selected = False
        self.items = items
        self.msg = msg
        self.multi = multi
        self.select = select
        super(_MultiSelect, self).__init__(
            title=title, ui_file=_UI_FILE, modal=True)

    def init_ui(self):
        """Init ui elements."""
        self.ui.Message.setText(self.msg)

        self.ui.Items.set_items(self.items)
        if self.select:

            _idxs = []
            if isinstance(self.select, list):
                for _item in self.select:
                    if _item in self.items:
                        _idxs.append(self.items.index(_item))
            else:
                raise ValueError(self.select)
            self.ui.Items.select_rows(_idxs)

        if not self.multi:
            raise NotImplementedError

    def _callback__Select(self):
        self.close()
        self.selected = True


def multi_select(
        items, msg='Select items:', multi=True, title='Multi select',
        select=None):
    """Launch multi select dialog.

    Args:
        items (list): list of items to select from
        msg (str): dialog message
        multi (bool): allow multiple selections
        title (str): dialog title
        select (any|list): item/items to select by default

    Returns:
        (any): selected item
    """
    _dialog = _MultiSelect(
        items=items, msg=msg, multi=multi, title=title, select=select)
    if not _dialog.selected:
        raise q_utils.DialogCancelled(_dialog)
    return _dialog.ui.Items.selected_texts()
