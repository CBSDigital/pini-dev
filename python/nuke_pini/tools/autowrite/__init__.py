"""Tools for managing the autowrite node."""

from pini import icons

from .aw_callbacks import (
    flush_callbacks, install_callbacks, knob_changed_callback,
    update_all)
from .aw_build import build
from .aw_node import CAutowrite2, get_selected

ICON = icons.find('Robot')
