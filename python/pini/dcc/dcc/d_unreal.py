"""Tools for managing unreal interaction via the pini.dcc module."""

# pylint: disable=import-error,abstract-method

import logging

import unreal

from pini.utils import abs_path

from .d_base import BaseDCC

_LOGGER = logging.getLogger(__name__)


class UnrealDCC(BaseDCC):
    """Manages interactions with unreal."""

    NAME = 'unreal'

    def cur_file(self):
        """Get path to current file.

        Returns:
            (str): current file
        """
        _dir = unreal.Paths.project_content_dir()
        _ss = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
        _world = _ss.get_editor_world()
        _name = _world.get_name()

        return abs_path('{}/{}.umap'.format(_dir, _name))
