"""Tools for managing unreal interaction via the pini.dcc module."""

# pylint: disable=import-error,abstract-method,c-extension-no-member

import logging

import unreal

from pini.utils import abs_path

from .d_base import BaseDCC

_LOGGER = logging.getLogger(__name__)


class UnrealDCC(BaseDCC):
    """Manages interactions with unreal."""

    NAME = 'unreal'

    section = None

    def add_menu_divider(self, parent, name):
        """Add menu divider to ui.

        Args:
            parent (str): parent menu
            name (str): uid for divider
        """
        _menu = _obt_menu(parent)
        _menu.add_section(name, unreal.Text("*"))
        self.section = name

    def add_menu_item(self, parent, command, image, label, name):
        """Add menu item to ui.

        Args:
            parent (str): parent menu
            command (func): command to call on item click
            image (str): path to item icon
            label (str): label for item
            name (str): uid for item
        """
        del image
        return _build_menu_item(
            parent=parent, cmd=command, name=name, label=label,
            section=self.section)

    def cur_file(self):
        """Get path to current file.

        Returns:
            (str): current file
        """
        _dir = unreal.Paths.project_content_dir()
        _ss = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
        _world = _ss.get_editor_world()
        _name = _world.get_name()

        return abs_path(f'{_dir}/{_name}.umap')

    def _read_version(self):
        """Read current unreal version.

        Returns:
            (tuple): version
        """
        _ver_s = unreal.SystemLibrary.get_engine_version()
        _LOGGER.debug(' - VER S %s', _ver_s)
        _idxs_s, _ = _ver_s.split('-', 1)
        _LOGGER.debug(' - IDXS S %s', _idxs_s)
        _idxs = tuple(int(_idx) for _idx in _idxs_s.split('.'))
        _LOGGER.debug(' - IDXS %s', _idxs)
        return _idxs


def _build_menu_item(name, cmd, label, parent, section=None, tooltip=None):
    """Build a menu item.

    Args:
        name (str): name/uid for item
        cmd (str): python command
        label (str): item label
        parent (str): parent menu
        section (str): item section
        tooltip (str): item tooltip

    Returns:
        (ToolMenuEntry): menu item
    """
    _menus = unreal.ToolMenus.get()
    _menu = _obt_menu(parent)
    _LOGGER.info(' - MENU %s', _menu)

    _menu_path = f"LevelEditor.MainMenu.{name}"
    _menus.remove_entry(_menu_path, name, name)

    _entry = unreal.ToolMenuEntry(
        name=name,
        type=unreal.MultiBlockType.MENU_ENTRY)
    _entry.set_label(label)
    if tooltip:
        _entry.set_tool_tip(tooltip)
    _entry.set_string_command(
        unreal.ToolMenuStringCommandType.PYTHON, "", cmd)

    _section = section or 'DefaultSection'
    _menu.add_menu_entry(_section, _entry)

    _menus.refresh_all_widgets()

    return _entry


def _obt_menu(name):
    """Obtain a menu, creating if needed.

    Args:
        name (str): menu name

    Returns:
        (ToolMenu): menu
    """
    _menus = unreal.ToolMenus.get()
    _main_menu = _menus.find_menu("LevelEditor.MainMenu")
    _LOGGER.info(' - MAIN MENU %s', _main_menu)
    _path = f"LevelEditor.MainMenu.{name}"

    if _menus.is_menu_registered(_path):
        _menu = _menus.find_menu(_path)
    else:
        _menu = _main_menu.add_sub_menu(
            _main_menu.menu_name, "", name, name, f"{name} tools")
        _menus.refresh_all_widgets()

    return _menu
