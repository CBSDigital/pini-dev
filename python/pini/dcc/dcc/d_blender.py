"""Tools for managing blender interaction via the pini.dcc module."""

# pylint: disable=abstract-method

import bpy

from pini.utils import abs_path, File

from . import d_base


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

    def _read_version(self):
        """Read application version tuple.

        If no patch is available, patch is returned as None.

        Returns:
            (tuple): major/minor/patch
        """
        return [int(_item) for _item in bpy.app.version_string.split('.')]

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
