"""Tools for managing substance interaction via the pini.dcc module."""

# pylint: disable=abstract-method

import logging

from substance_painter import project, exception

from pini.utils import abs_path, to_str

from .d_base import BaseDCC

_LOGGER = logging.getLogger(__name__)


class SubstanceDCC(BaseDCC):
    """Manages interactions with substance."""

    NAME = 'substance'
    DEFAULT_EXTN = 'spp'

    def cur_file(self):
        """Get path to current file.

        Returns:
            (str): current file
        """
        _LOGGER.info('CUR FILE')
        try:
            _path = project.file_path()
        except exception.ProjectError:
            return None
        _LOGGER.info(' - PATH %s', _path)
        return abs_path(_path)

    def _force_save(self, file_=None):
        """Force save the current scene without overwrite confirmation.

        Args:
            file_ (str): path to save scene to
        """
        _file = to_str(file_) or self.cur_file()
        project.save_as(_file, mode=project.ProjectSaveMode.Incremental)

    def get_scene_data(self, key):
        """Retrieve data stored with this scene.

        Args:
            key (str): data to obtain

        Returns:
            (any): data which has been stored in the scene
        """
        return None

    def t_range(self, **kwargs):  # pylint: disable=unused-argument
        """Get start/end frames.

        Returns:
            (None): N/A
        """
        return None
