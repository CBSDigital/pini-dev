"""Tools for managing the QMenu wrapper."""

import logging

from pini import icons, dcc
from pini.utils import (
    copy_text, wrap_fn, chain_fns, File, Video, null_fn)

from ...q_mgr import QtWidgets
from ...q_utils import to_icon

_LOGGER = logging.getLogger(__name__)


class CMenu(QtWidgets.QMenu):
    """Wrapper for CMenu."""

    def add_action(self, text, func, icon=None, enabled=True):
        """Add an action to the menu.

        Args:
            text (str): action text
            func (fn): action callback
            icon (str): path to action icon
            enabled (bool): action enabled state

        Returns:
            (QAction): new action
        """
        from pini import qt
        from pini.tools import error

        # Execute add action
        _catcher = error.get_catcher(qt_safe=True)
        _func = _catcher(func)
        _args = [text, _func]
        if icon:
            _pix = icon
            if isinstance(_pix, str):
                _pix = qt.obt_pixmap(icon)
            _args = [_pix] + _args
        _action = self.addAction(*_args)

        if not enabled:
            _action.setEnabled(False)

        return _action

    def add_dir_actions(self, dir_):
        """Add actions for a directory (eg. copy path, open in explorer).

        Args:
            dir_ (Dir): directory to add options for
        """
        self.add_action(
            'Copy path', wrap_fn(copy_text, dir_.path), icon=icons.COPY)
        self.add_action(
            'Open in explorer', dir_.browser, icon=icons.BROWSER)

    def add_file_actions(
            self, file_, delete_callback=None, delete=True, edit=True):
        """Add actions for a file (eg. copy path, open dir in explorer).

        Args:
            file_ (File): file to add options for
            delete_callback (fn): additional callback to run on deletion
            delete (bool): add delete action
            edit (bool): add edit action (if available)
        """
        _file = file_
        if isinstance(_file, str):
            _file = File(file_)
        _exists = _file.exists()
        self.add_action(
            'Copy path', wrap_fn(copy_text, _file.path), icon=icons.COPY)
        self.add_action(
            'Open dir in explorer', _file.browser, icon=icons.BROWSER)

        if delete:
            _delete_fn = _file.delete
            if delete_callback:
                _delete_fn = chain_fns(_delete_fn, delete_callback)
            self.add_action(
                'Delete', _delete_fn, icon=icons.DELETE)

        if edit and _file.is_editable():
            self.add_action(
                'Edit file', _file.edit, icon=icons.EDIT, enabled=_exists)
        if _file.extn in dcc.VALID_EXTNS:
            self.add_action(
                'Load scene', wrap_fn(dcc.load, _file), icon=icons.LOAD,
                enabled=_exists)

    def add_seq_actions(self, seq, delete_callback=None, delete=True):
        """Add actions for an image sequence.

        Args:
            seq (Seq): sequence to add options for
            delete_callback (fn): additional callback to run on deletion
            delete (bool): add delete action
        """
        _exists = seq.exists()
        self.add_action(
            'Copy path', wrap_fn(copy_text, seq.path), icon=icons.COPY)
        self.add_action(
            'Open dir in explorer', seq.browser, icon=icons.BROWSER)

        _delete_fn = seq.delete
        if delete_callback:
            _delete_fn = chain_fns(_delete_fn, delete_callback)

        if delete:
            self.add_action(
                'Delete', _delete_fn, icon=icons.DELETE)
        self.add_action(
            'View', seq.view, icon=icons.find("Play Button"))

    def add_video_actions(self, video, delete_callback=None, delete=True):
        """Add actions for a video file.

        Args:
            video (Video): video to add actions for
            delete_callback (fn): additional callback to run on deletion
            delete (bool): add delete action
        """
        assert isinstance(video, Video)
        self.add_file_actions(
            video, delete_callback=delete_callback, delete=delete)
        self.add_action(
            'View', video.view, icon=icons.find("Play Button"))

    def add_label(self, text, icon=None):
        """Add an action as a label.

        The action is disabled and only displays text.

        Args:
            text (str): text to display
            icon (str): path to icon

        Returns:
            (QAction): new action
        """
        _action = self.add_action(text=text, func=null_fn, icon=icon)
        _action.setEnabled(0)
        return _action

    def add_menu(self, label, icon=None, enabled=True):
        """Add sub menu to this menu.

        Args:
            label (str): menu label
            icon (str): path to menu icon
            enabled (bool): enabled state of menu

        Returns:
            (CMenu): sub menu
        """
        _menu = CMenu(label)
        self.addMenu(_menu)
        if icon:
            _menu.set_icon(icon)
        if not enabled:
            _menu.setEnabled(False)
        return _menu

    def add_separator(self):
        """Add separator."""
        self.addSeparator()

    def prune_items(self, name):
        """Remove items with matching object name.

        Args:
            name (str): object name to remove
        """
        for _action in self.actions():
            if _action.objectName() == name:
                _LOGGER.debug(' - REMOVE EXISTING ACTION %s %s', name, _action)
                _action.deleteLater()

    def set_icon(self, icon):
        """Set this menu's icon.

        Args:
            icon (str): path to icon
        """
        _icon = to_icon(icon)
        self.setIcon(_icon)
