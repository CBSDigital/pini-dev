"""Tools for managing custom qt interfaces."""

from pini import dcc

from .qc_ui_base import CUiBase
from .qc_ui_dialog import CUiDialog
from .qc_ui_main_window import CUiMainWindow

if dcc.NAME == 'maya':
    from .qc_mixin import CDockableMixin
    from .qc_ui_mixin import CUiDockableMixin
