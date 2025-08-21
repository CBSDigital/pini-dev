"""Tools for managing qt."""

import sys
from pini import dcc

from .custom import CUiDialog, CUiBase, CUiMainWindow, connect_callbacks
from .wrapper import (
    CPixmap, CListWidget, CListWidgetItem, CTabWidget, CComboBox, CLineEdit,
    CTreeWidget, CTreeWidgetItem, CColor, CProgressBar, CMenu, CPainter,
    CLabel, CSettings, CBaseWidget, CPointF, CHLine, CVLine, CSplitter,
    CListViewPixmapItem, CListViewWidgetItem, CListView, CPixmapLabel,
    TEST_IMG, CPoint, CTileWidget, CTileWidgetItem, CSlider, CVector2D,
    CSizeF, PIXMAP_EXTNS, CCheckBox, CSpinBox, CSize, CRectF, CRect,
    CIconButton)

from .q_const import BOLD_COLS, PASTEL_COLS
from .q_layout import find_layout_widgets, delete_layout, flush_layout
from .q_mgr import (
    QtGui, QtWidgets, QtCore, Qt, QtUiTools, LIB, LIB_VERSION,
    shiboken)
from .q_style import set_dark_style
from .q_ui_container import CUiContainer
from .q_ui_loader import build_ui_loader

from .q_utils import (
    to_p, safe_timer_event, to_size, to_rect, to_font, SavePolicy,
    get_application, close_all_interfaces, to_col, to_pixmap,
    X_AXIS, Y_AXIS, SETTINGS_DIR, to_icon, find_widget_children,
    set_application_icon, DialogCancelled, widget_to_signal, obt_icon,
    flush_dialog_stack, obt_pixmap, build_tmp_icon, p_is_onscreen,
    block_signals)

from .tools import (
    file_browser, input_dialog, raise_dialog, ok_cancel, yes_no_cancel,
    notify, progress_bar, progress_dialog, warning, multi_select,
    close_all_progress_bars)

from .graph import (
    CGraphSpace, CGraphWindow, CGBasicElem, CGPixmapElem, CGMoveElem,
    CGTextElem, CGIconElem, CGStretchElem)
from .graph_2 import (
    PNGNode, PNGNodeGraph, PNGImgNode, PNGRectNode, PNGRectImgNode)

if dcc.NAME == 'maya':
    from .custom import CUiDockableMixin, CDockableMixin

# Set up dialog stack for tracking interfaces
if not hasattr(sys, 'QT_DIALOG_STACK'):
    sys.QT_DIALOG_STACK = {}
if not hasattr(sys, 'QT_PROGRESS_BAR_STACK'):
    sys.QT_PROGRESS_BAR_STACK = []
