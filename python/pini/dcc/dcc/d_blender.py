"""Tools for managing blender interaction via the pini.dcc module."""

# pylint: disable=abstract-method

import logging

import bpy

from pini.utils import abs_path, File

from . import d_base

_LOGGER = logging.getLogger(__name__)


class BlenderDCC(d_base.BaseDCC):
    """Manages interactions with blender."""

    DEFAULT_EXTN = 'blend'
    HELPER_AVAILABLE = True
    NAME = 'blender'
    VALID_EXTNS = ('blend', )

    def cur_file(self):
        """Get path to current file.

        Returns:
            (str|None): current file (if any)
        """
        return abs_path(bpy.data.filepath)

    def _force_load(self, file_):
        """Force load the given scene.

        Args:
            file_ (str): scene to load
        """
        _file = File(file_)
        bpy.ops.wm.open_mainfile(filepath=_file.path)

    def _force_save(self, file_=None):
        """Force save the current scene without overwrite confirmation.

        Args:
            file_ (str): path to save scene to
        """
        _file = File(file_ or self.cur_file())
        bpy.ops.wm.save_as_mainfile(filepath=_file.path)

    def get_scene_data(self, key):
        """Retrieve data stored with this scene.

        Args:
            key (str): data to obtain

        Returns:
            (any): data which has been stored in the scene
        """
        _LOGGER.debug('GET SCENE DATA %s', key)
        return bpy.context.scene.get(key)

    def _read_version(self):
        """Read application version tuple.

        If no patch is available, patch is returned as None.

        Returns:
            (tuple): major/minor/patch
        """
        return [int(_item) for _item in bpy.app.version_string.split('.')]

    def set_scene_data(self, key, val):
        """Store data within this scene.

        Args:
            key (str): name of data to store
            val (any): value of data to store
        """
        _LOGGER.debug('SET SCENE DATA key=%s val=%s', key, val)
        bpy.context.scene[key] = val

    def t_end(self, class_=float):
        """Get end frame.

        Args:
            class_ (class): override result type

        Returns:
            (float): end time
        """
        return class_(bpy.context.scene.frame_end)

    def t_start(self, class_=float):
        """Get start frame.

        Args:
            class_ (class): override result type

        Returns:
            (float): start time
        """
        return class_(bpy.context.scene.frame_start)

    def unsaved_changes(self):
        """Test whether the current scene has unsaved changes.

        Returns:
            (bool): unsaved changes
        """
        return bpy.data.is_dirty
