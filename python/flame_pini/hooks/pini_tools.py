"""Hooks for installing pini tools to flame.

This file's folder should be added to $DL_PYTHON_HOOK_PATH and then flame
will read it on startup. It embed pini tools into the right-click media menu.
"""

import logging
import os
import sys

_LOGGER = logging.getLogger(__name__)


def _export_as_plates(selection):
    """Callback for export as plates tool.

    Args:
        selection (PySequence list): selected sequence nodes
    """
    _py3_path = os.environ.get('PINI_PY3_PATH')
    if _py3_path:
        while _py3_path in sys.path:
            sys.path.remove(_py3_path)
        sys.path.append(_py3_path)
    from flame_pini import f_pipe
    f_pipe.export_sequences_to_plates(selection)


def get_media_panel_custom_ui_actions():
    """Get media panel custom ui actions.

    This is a function that flame looks for and uses to build the
    right-click media menu.

    Returns:
        (dict): menu information
    """
    return [{
        "name": "Carbon Pipeline",
        "actions": [{"name": "Export as plates",
                     "execute": _export_as_plates,
                     "waitCursor": False}],
    }]
