"""Tools for managing simple QMessageBox wrappers."""

import logging

import six

from pini import icons
from pini.utils import lprint

from ..q_mgr import QtWidgets, QtGui, QtCore
from .. import q_utils

_LOGGER = logging.getLogger(__name__)


class _CMessageBox(QtWidgets.QMessageBox):
    """Base class for any managed message boxes."""

    def __init__(
            self, text, title, buttons, icon=None, icon_size=None,
            parent=None):
        """Constructor.

        Args:
            text (str): message box text
            title (str): message box title
            buttons (str list): message box buttons
            icon (str): message box icon
            icon_size (tuple): icon size
            parent (QDialog): parent dialog
        """
        from pini import dcc

        _parent = parent or dcc.get_main_window_ptr()
        _args = [_parent] if _parent else []
        super(_CMessageBox, self).__init__(*_args)
        self.setWindowTitle(title)
        self.setText(text)

        self.buttons, self.shortcuts = self._set_buttons(buttons)

        if icon:
            self._set_icon(icon=icon, icon_size=icon_size)

        self._force_result = None

    def _set_buttons(self, buttons):
        """Set ui buttons.

        Args:
            buttons (str list): buttons to add

        Returns:
            (list, dict): buttons, shortcuts
        """

        # Create buttons
        _buttons = list(buttons)
        _btn_map = {}
        for _button in _buttons:
            _btn_map[_button] = self.addButton(
                _button, QtWidgets.QMessageBox.AcceptRole)

        # Make sure we have cancel behaviour
        if "Cancel" not in _btn_map:
            _btn_map["Cancel"] = self.addButton(
                "Cancel", QtWidgets.QMessageBox.AcceptRole)
            _btn_map["Cancel"].hide()
            _buttons += ["Cancel"]
        self.setEscapeButton(_btn_map["Cancel"])
        self.setDefaultButton(_btn_map["Cancel"])

        # Read shortcuts
        _shortcuts = {}
        for _button in _buttons:
            if _button == 'Cancel':
                continue
            if _button[0] not in _shortcuts:
                _shortcuts[_button[0]] = _button
            else:
                del _shortcuts[_button[0]]

        return _buttons, _shortcuts

    def _set_icon(self, icon, icon_size):
        """Set message box icon.

        Args:
            icon (str): path to icon
            icon_size (tuple): icon size
        """
        if isinstance(icon, six.string_types):
            _pixmap = QtGui.QPixmap(icon)
        elif isinstance(icon, QtGui.QPixmap):
            _pixmap = icon
        else:
            raise ValueError(_pixmap)
        if icon_size is None:
            if _pixmap.width() == 144 and _pixmap.height() == 144:
                icon_size = 72
        if icon_size:
            from pini import qt
            _pixmap = qt.CPixmap(_pixmap).resize(icon_size)
        self.setIconPixmap(_pixmap)

    def get_result(self):
        """Get message box result.

        Returns:
            (str): label of button that was clicked
        """
        _exec_result = self.exec_()
        if self._force_result:
            _result = self._force_result
        else:
            _result = self._force_result or self.buttons[_exec_result]
        if _result == "Cancel":
            raise q_utils.DialogCancelled
        return _result

    def keyPressEvent(self, event):
        """Triggered by key press.

        Args:
            event (QKeyEvent): triggered event
        """
        _key = chr(event.key()) if event.key() < 256 else None
        _alt = event.modifiers() == QtCore.Qt.AltModifier
        if _key and _alt and _key in self.shortcuts:
            _result = self.shortcuts[_key]
            self._force_result = _result
            self.close()


def ok_cancel(
        msg, title='Confirm', icon=None, parent=None,
        verbose=1):
    """Message box with ok and cancel buttons.

    If ok is clicked nothing happens, if cancel is selected then
    an error is thrown.

    Args:
        msg (str): interface message
        title (str): interface title
        icon (str): path to icon
        parent (QDialog): parent dialog
        verbose (int): print process data
    """
    raise_dialog(
        msg=msg, title=title, verbose=verbose, parent=parent,
        icon=icon or icons.find('Tiger'))


def notify(
        msg, title='Notification', icon=None, parent=None,
        verbose=1):
    """Raise notification dialog with "Ok" button.

    Args:
        msg (str): interface message
        title (str): interface title
        icon (str): path to icon
        parent (QDialog): parent dialog
        verbose (int): print process data
    """
    raise_dialog(
        msg=msg, title=title, icon=icon or icons.find('Panda'), verbose=verbose,
        buttons=('Ok', ), parent=parent)


def raise_dialog(
        msg="No message set", title="Dialog", buttons=("Ok", "Cancel"),
        icon=None, icon_size=None, parent=None, verbose=1):
    """Raise simple message box dialog.

    Args:
        msg (str): interface message
        title (str): interface title
        buttons (str tuple): interface buttons
        icon (str): path to icon
        icon_size (tuple): icon size
        parent (QDialog): parent dialog
        verbose (int): print process data

    Returns:
        (str): text from selected button
    """
    from pini import dcc, qt

    # Avoid farm qt seg fault
    if dcc.batch_mode():
        lprint('MESSAGE:\n'+msg)
        raise RuntimeError("Cannot raise dialog in batch mode - "+title)
    qt.get_application()

    # Build dialog
    _icon = icon or icons.find('Bear')
    _box = _CMessageBox(
        title=title, text=msg, buttons=buttons, icon=_icon,
        icon_size=icon_size, parent=parent)
    if verbose:
        _LOGGER.info(msg)

    return _box.get_result()


def yes_no_cancel(msg, title='Confirm', icon=None, parent=None):
    """Raise yes/no/cancel dialog.

    Args:
        msg (str): interface message
        title (str): interface title
        icon (str): override icon to apply
        parent (QDialog): parent dialog

    Returns:
        (bool): whether yes was selected
    """
    _result = raise_dialog(
        msg, buttons=['Yes', 'No', 'Cancel'], title=title, parent=parent,
        icon=icon or icons.find('Tiger'))
    if _result == 'Yes':
        return True
    if _result == 'No':
        return False
    raise ValueError(_result)
