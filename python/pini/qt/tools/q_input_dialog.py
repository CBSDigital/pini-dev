"""Tools for getting an input from the user."""

import logging

from .. import q_utils
from ..q_mgr import QtWidgets

_LOGGER = logging.getLogger(__name__)


def _find_ok_button(dialog):
    """Find the OK push button on an input dialog.

    Args:
        dialog (QInputDialog): dialog to search

    Returns:
        (QPushButton|None): OK button if found
    """
    _button_box = dialog.findChild(QtWidgets.QDialogButtonBox)
    if _button_box:
        return _button_box.button(QtWidgets.QDialogButtonBox.Ok)

    # Some hosts (eg. hou) may not expose a QDialogButtonBox child
    for _btn in dialog.findChildren(QtWidgets.QPushButton):
        if _btn.text().replace('&', '') in ('OK', 'Ok'):
            return _btn
    return None


def input_dialog(
        msg="Enter text here:", title="Enter Text", default='',
        width=300, parent=None):
    """Launch input dialog to request text data from the user.

    Args:
        msg (str): dialog message
        title (str): dialog title
        default (str): default value for dialog
        width (int): override width
        parent (QDialog): parent dialog

    Returns:
        (str): dialog result
    """
    from pini import dcc

    _LOGGER.debug('INPUT DIALOG')
    q_utils.get_application()

    _parent = parent or dcc.get_main_window_ptr()
    _LOGGER.debug(' - PARENT %s', _parent)
    _args = [_parent] if _parent else []

    # Build input dialog
    _dialog = QtWidgets.QInputDialog(*_args)
    _dialog.setInputMode(QtWidgets.QInputDialog.TextInput)
    _dialog.setWindowTitle(title)
    _dialog.setLabelText(msg)
    _dialog.setTextValue(default)
    _dialog.resize(width, 100)

    # Make Enter accept (hou often breaks default-button routing)
    _line_edit = _dialog.findChild(QtWidgets.QLineEdit)
    if _line_edit:
        _line_edit.returnPressed.connect(_dialog.accept)
    _ok = _find_ok_button(_dialog)
    if _ok:
        _ok.setDefault(True)
        _ok.setAutoDefault(True)

    _responded = _dialog.exec_()
    _result = str(_dialog.textValue())

    if _responded in [0, False]:
        raise q_utils.DialogCancelled

    return _result
