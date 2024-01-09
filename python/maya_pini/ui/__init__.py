"""Tools for managing interfaces in maya."""

from .mui_misc import (
    clear_script_editor, get_main_window, get_main_window_ptr,
    obtain_menu, add_menu_item, find_ctrl, get_active_model_editor,
    get_active_cam, find_menu, raise_attribute_editor, find_window,
    reset_window, add_menu_divider)
from .mui_shelf import (
    add_shelf_button, obtain_shelf, flush_shelf, find_shelf_buttons,
    find_shelf_button, add_shelf_separator)
from .mui_vp import set_vp, MODEL_EDITOR_ATTRS
