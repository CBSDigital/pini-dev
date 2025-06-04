"""Tools for managing substance interaction via the pini.dcc module."""

# pylint: disable=abstract-method

import logging
import win32api

from substance_painter import project, exception

from pini.utils import abs_path, to_str, wrap_fn, find_exe

from .d_base import BaseDCC

_LOGGER = logging.getLogger(__name__)


class SubstanceDCC(BaseDCC):
    """Manages interactions with substance."""

    NAME = 'substance'
    DEFAULT_EXTN = 'spp'
    VALID_EXTNS = 'spp'

    def add_menu_divider(self, parent, name):
        """Add menu divider to maya ui.

        Args:
            parent (str): parent menu
            name (str): uid for divider
        """
        from substance_pini import ui
        _menu = ui.obt_menu(parent)
        _menu.prune_items(name=name)
        _menu.add_separator()

    def add_menu_item(self, parent, command, image, label, name):
        """Add menu item to maya ui.

        Args:
            parent (str): parent menu
            command (func): command to call on item click
            image (str): path to item icon
            label (str): label for item
            name (str): uid for item
        """
        from pini import qt
        from substance_pini import ui

        _LOGGER.debug('ADD MENU ITEM %s', name)

        _menu = ui.obt_menu(parent)
        _menu.prune_items(name=name)

        _icon = None
        if image:
            _icon = qt.CPixmap(100, 100)
            _icon.fill('Transparent')
            _scale = 80
            _icon.draw_overlay(
                image, (50 + (100 - _scale) / 2, 50), anchor='C', size=90)

        _action = _menu.add_action(label, wrap_fn(exec, command), icon=_icon)
        _action.setObjectName(name)
        _LOGGER.debug(' - CREATED ACTION %s %s', name, _action)

        return _action

    def _build_export_handlers(self):
        """Initiate export handlers."""
        from pini.dcc import export
        _handlers = super()._build_export_handlers()
        _handlers += [
            export.CSubstanceTexturePublish(),
        ]
        return _handlers

    def cur_file(self):
        """Get path to current file.

        Returns:
            (str): current file
        """
        _LOGGER.debug('CUR FILE')
        try:
            _path = project.file_path()
        except exception.ProjectError:
            return None
        _LOGGER.debug(' - PATH %s', _path)
        return abs_path(_path)

    def _force_load(self, file_):
        """Force load the given scene.

        Args:
            file_ (str): scene to load
        """
        _file_s = to_str(file_)
        project.open(_file_s)

    def _force_save(self, file_=None):
        """Force save the current scene without overwrite confirmation.

        Args:
            file_ (str): path to save scene to
        """
        _file = to_str(file_) or self.cur_file()
        project.save_as(_file, mode=project.ProjectSaveMode.Incremental)

    def get_main_window_ptr(self):
        """None if no dcc."""
        from substance_pini import ui
        return ui.to_main_window()

    def get_scene_data(self, key):  # pylint: disable=unused-argument
        """Retrieve data stored with this scene.

        Args:
            key (str): data to obtain

        Returns:
            (any): data which has been stored in the scene
        """
        return None

    def _read_version(self):
        """Read application version tuple.

        If no patch is available, patch is returned as None.

        Returns:
            (tuple): major/minor/patch
        """
        _LOGGER.debug('READ VERSION %s', self)
        _exe = find_exe('Adobe Substance 3D Painter')
        if not _exe:
            return None
        _path = _exe.path
        _LOGGER.debug(' - PATH %s', _path)
        _ver_s = win32api.GetFileVersionInfo(
            _path, r'\StringFileInfo\040904B0\FileVersion')
        return tuple(int(_val) for _val in _ver_s.split('.'))

    def set_scene_data(self, key, val):
        """Store data within this scene.

        Args:
            key (str): name of data to store
            val (any): value of data to store
        """

    def t_frame(self, class_=float):  # pylint: disable=unused-argument
        """Obtain current frame.

        Args:
            class_ (class): override type of data to return (eg. int)

        Returns:
            (float): current frame
        """
        return None

    def t_range(self, *args, **kwargs):  # pylint: disable=unused-argument
        """Get start/end frames.

        Returns:
            (None): N/A
        """
        return None

    def unsaved_changes(self):
        """Test whether the current scene has unsaved changes.

        Returns:
            (bool): unsaved changes
        """
        if not self.cur_file():
            return False
        return project.needs_saving()
