"""Tools for getting an input from the user."""

from .. import q_utils
from ..q_mgr import QtWidgets


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
    q_utils.get_application()

    _args = [parent] if parent else []

    # Build input dialog
    _dialog = QtWidgets.QInputDialog(*_args)
    _dialog.setInputMode(QtWidgets.QInputDialog.TextInput)
    _dialog.setWindowTitle(title)
    _dialog.setLabelText(msg)
    _dialog.setTextValue(default)
    _dialog.resize(width, 100)

    _responded = _dialog.exec_()
    _result = str(_dialog.textValue())

    if _responded in [0, False]:
        raise q_utils.DialogCancelled

    return _result
