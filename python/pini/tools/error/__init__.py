"""Tools for handling errors."""

from .ce_catcher import catch, get_catcher, toggle
from .ce_error import CEError
from .ce_tools import continue_on_fail, HandledError

# Allow import without qt available
try:
    from .ce_dialog import UI_FILE, launch_ui
except ImportError:
    pass
