"""Tools for handling errors."""

from .e_catcher import catch, get_catcher, toggle
from .e_error import PEError, error_from_str
from .e_tools import continue_on_fail, HandledError, FileError
from .e_trace_line import PETraceLine

# Allow import without qt available
try:
    from .e_dialog import UI_FILE, launch_ui
except ImportError:
    pass

TRIGGERED = False
