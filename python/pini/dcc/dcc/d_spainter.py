"""Tools for managing substance painter interaction."""

# pylint: disable=abstract-method

import logging

import substance_painter
from substance_painter import project, exception, application

from pini.utils import abs_path, to_str, wrap_fn

from .d_base import BaseDCC

_LOGGER = logging.getLogger(__name__)
_META_CONTEXT = 'pini'


class SubstancePainterDCC(BaseDCC):
    """Manages interactions with substance painter."""

    NAME = 'spainter'
    DEFAULT_EXTN = 'spp'
    VALID_EXTNS = 'spp'

    def add_menu_divider(self, parent, name):
        """Add menu divider to maya ui.

        Args:
            parent (str): parent menu
            name (str): uid for divider
        """
        from spainter_pini import ui
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
        from spainter_pini import ui

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

    def _build_exporters(self):
        """Initiate export handlers."""
        from pini.dcc import export
        _handlers = super()._build_exporters()
        _handlers += [
            export.CSPainterTexturePublish(),
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
        if self.cur_file():
            substance_painter.project.close()
        project.open(_file_s)

    def _force_new_scene(self):
        """Force new scene in current dcc."""
        from pini.tools import error
        raise error.HandledError(
            'Substance does not support empty scenes.\n\nYou need to open '
            'an fbx file.')

    def _force_save(self, file_=None, selection=False):
        """Force save the current scene without overwrite confirmation.

        Args:
            file_ (str): path to save scene to
            selection (bool): export only selection
        """
        from pini.tools import error
        if selection:
            raise NotImplementedError
        _file = to_str(file_) or self.cur_file()
        try:
            project.save_as(_file, mode=project.ProjectSaveMode.Incremental)
        except exception.ProjectError as _exc:
            if str(_exc) == 'Cannot save because no project is opened.':
                raise error.HandledError(
                    'Unable to save because no project is open') from _exc
            raise _exc

    def get_main_window_ptr(self):
        """None if no dcc."""
        from spainter_pini import ui
        return ui.to_main_window()

    def get_scene_data(self, key):  # pylint: disable=unused-argument
        """Retrieve data stored with this scene.

        Args:
            key (str): data to obtain

        Returns:
            (any): data which has been stored in the scene
        """
        _meta = _to_metadata()
        if not _meta or key not in _meta.list():
            return None
        _val = _meta.get(key)
        _LOGGER.debug('GET SCENE DATA %s %s', key, _val)
        return _val

    def _read_version(self):
        """Read application version tuple.

        If no patch is available, patch is returned as None.

        Returns:
            (tuple): major/minor/patch
        """
        _LOGGER.debug('READ VERSION %s', self)
        return application.version_info()

    def set_scene_data(self, key, val):
        """Store data within this scene.

        Args:
            key (str): name of data to store
            val (any): value of data to store
        """
        _meta = _to_metadata()
        if not _meta:
            _LOGGER.debug(' - SET METADATA FAILED, NO PROJ OPEN')
            return
        if val is not None and not isinstance(val, (bool, int, float, str, list, dict)):
            raise TypeError(f'Unsupported scene data type {key} {type(val).__name__}')
        _LOGGER.debug('SET SCENE DATA %s %s', key, val)
        _meta.set(key, val)

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

    def take_snapshot(self, file_):
        """Take snapshot of the current scene.

        Args:
            file_ (str): path to save image to
        """
        from spainter_pini import p_pipe
        return p_pipe.take_snapshot(file_, force=True)

    def unsaved_changes(self):
        """Test whether the current scene has unsaved changes.

        Returns:
            (bool): unsaved changes
        """
        if not self.cur_file():
            return False
        return project.needs_saving()


def _to_metadata():
    """Obtain pini metadata store for the current project (None if no project)."""
    if not project.is_open():
        return None
    return project.Metadata(_META_CONTEXT)
