"""Tools for managing the error catcher dialog."""

import logging

from pini import icons, qt
from pini.utils import File, email

from . import e_error

_LOGGER = logging.getLogger(__name__)
_DIR = File(__file__).to_dir()

EMOJI = icons.EMOJI.find_emoji("Lemon")
ICON = EMOJI.path
UI_FILE = _DIR.to_file('error_catcher.ui')


class _ErrorCatcherUi(qt.CUiDialog):
    """Dialog to notify user that an error has occurred."""

    error = None

    def __init__(self, error=None, parent=None, show=True, stack_key=None):
        """Constructor.

        Args:
            error (PEError): override error that triggered ui
            parent (QDialog): parent dialog
            show (bool): show the ui
            stack_key (str): override stack key
                (to allow multiple error dialogs)
        """
        super().__init__(
            ui_file=UI_FILE, load_settings=False, parent=parent,
            catch_errors=False, show=show, stack_key=stack_key)
        self.set_window_icon(ICON)

        self.set_error(error or e_error.PEError(), trigger=False)

    def set_error(self, error_, trigger=True):
        """Apply the given error to the ui.

        Args:
            error_ (PEError): error to apply
            trigger (bool): apply triggered global
        """
        _LOGGER.warning('APPLYING ERROR %s', error_)
        from pini.tools import error
        if trigger:
            error.TRIGGERED = True

        self.error = error_

        self._redraw__Label()
        self.ui.Lines.redraw()

        self.ui.SendEmail.setEnabled(
            bool(email.FROM_EMAIL and email.SUPPORT_EMAIL))

    def _redraw__Label(self):
        if self.error.type_name:
            _text = '\n'.join([
                f'There has been an error ({self.error.type_name}):'
                '',
                f'{self.error.message}',
            ])
        else:
            _text = ''
        self.ui.Label.setText(_text)

    def _redraw__Lines(self):
        _items = []
        for _line in reversed(self.error.lines):
            _item = qt.CListWidgetItem(_line.to_text(), data=_line)
            _items.append(_item)
        self.ui.Lines.set_items(_items)

    def _callback__ViewCode(self):
        _line = self.ui.Lines.selected_data()
        _line.view_code()

    def _callback__SendEmail(self):
        self.error.send_email()
        self.close()


def launch_ui(error=None, parent=None, show=True, stack_key=None):
    """Launch error catcher dialog.

    Args:
        error (PEError): override error that triggered ui
        parent (QDialog): parent dialog
        show (bool): show the ui
        stack_key (str): override stack key (to allow multiple error dialogs)

    Returns:
        (ErrorCatcherUi): dialog instance
    """
    from pini.tools import error as _mod
    _mod.DIALOG = _ErrorCatcherUi(
        error=error, parent=parent, show=show, stack_key=stack_key)
    return _mod.DIALOG
