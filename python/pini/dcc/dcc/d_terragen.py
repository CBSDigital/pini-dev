"""Tools for managing terragen interaction via the pini.dcc module."""

# pylint: disable=import-error,abstract-method

import logging

import terragen_rpc as tg

from pini.utils import abs_path, to_str

from .d_base import BaseDCC

_LOGGER = logging.getLogger(__name__)


class TerragenDCC(BaseDCC):
    """Manages interactions with terragen."""

    NAME = 'terragen'
    DEFAULT_EXTN = 'tgd'
    VALID_EXTNS = ('tgd', )

    def cur_file(self):
        """Get path to current file.

        Returns:
            (str): current file
        """
        return abs_path(tg.project_filepath())

    def get_scene_data(self, key):
        """Retrieve data stored with this scene.

        Args:
            key (str): data to obtain

        Returns:
            (any): data which has been stored in the scene
        """
        return None

    def _force_load(self, file_):
        """Force load the given scene.

        Args:
            file_ (str): scene to load
        """
        _file = to_str(file_)
        tg.open_project(_file)

    def _force_new_scene(self):
        """Force new scene."""
        tg.new_project()

    def _force_save(self, file_=None):
        """Force save the current scene without overwrite confirmation.

        Args:
            file_ (str): path to save scene to
        """
        _file = to_str(file_) or self.cur_file()
        _LOGGER.info('SAVE %s', _file)
        tg.save_project(_file)

    def set_scene_data(self, key, val):
        """Store data within this scene.

        Args:
            key (str): name of data to store
            val (any): value of data to store
        """

    def t_end(self, class_=int):
        """Get timeline end frame.

        Args:
            class_ (class): override result type

        Returns:
            (int): end time
        """
        _result = tg.root().get_param_as_int('end_frame')
        return class_(_result)

    def t_start(self, class_=int):
        """Get timeline start frame.

        Args:
            class_ (class): override result type

        Returns:
            (int): start time
        """
        _result = tg.root().get_param_as_int('start_frame')
        return class_(_result)

    def unsaved_changes(self):
        """Test whether the current scene has unsaved changes.

        Returns:
            (bool): unsaved changes
        """
        return False
