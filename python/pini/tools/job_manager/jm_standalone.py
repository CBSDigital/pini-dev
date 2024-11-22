"""Standalone launcher for shot manager.

NOTE: this should be run using python3 as PySide is missing
some of the required QComboBox slots.
"""

import os
import sys

from pini import qt

from . import jm_dialog


def launch_standalone():
    """Launch ShotManager standalone application."""
    assert sys.version_info.major == 3

    print(f'LAUNCH SHOT MANAGER STANDALONE {os.name}')

    # Prepare icon - needs to happen before ui displayed
    if os.name == 'nt':
        import ctypes
        _name = 'ShotManagerB'
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(_name)

    _app = qt.get_application()
    qt.set_dark_style()

    # Launch dialog
    _dialog = jm_dialog.launch()
    _icon = qt.to_icon(jm_dialog.ICON)
    _app.setWindowIcon(_icon)
    _app.exec_()
    _dialog.save_settings()
    print('SHOT MANAGER COMPLETE')


if __name__ == '__main__':

    launch_standalone()
