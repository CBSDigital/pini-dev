"""Tools for managing substance interaction via the pini.dcc module."""

# pylint: disable=abstract-method

import logging

import substance_painter
from substance_painter import project, exception

from pini.utils import abs_path, to_str

from .d_base import BaseDCC

_LOGGER = logging.getLogger(__name__)


class SubstanceDCC(BaseDCC):
    """Manages interactions with substance."""

    NAME = 'substance'
    DEFAULT_EXTN = 'spp'
    VALID_EXTNS = 'spp'

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
        return substance_painter.ui.get_main_window()

    def get_scene_data(self, key):  # pylint: disable=unused-argument
        """Retrieve data stored with this scene.

        Args:
            key (str): data to obtain

        Returns:
            (any): data which has been stored in the scene
        """
        return None

    def set_scene_data(self, key, val):
        """Store data within this scene.

        Args:
            key (str): name of data to store
            val (any): value of data to store
        """

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
