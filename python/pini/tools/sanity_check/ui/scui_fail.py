"""Tools for managing the fail item ui element."""

import logging

from pini import qt
from pini.qt import Qt, QtWidgets, QtGui
from pini.tools import error
from pini.utils import chain_fns

_LOGGER = logging.getLogger(__name__)


class SCUiFailItem(qt.CListViewWidgetItem):  # pylint: disable=too-many-instance-attributes
    """Represents a check failure in the ui."""

    btns = None
    label = None

    def __init__(self, list_view, fail, run_check):
        """Constructor.

        Args:
            list_view (CListView): parent list view
            fail (SCFail): fail item
            run_check (fn): callback to rerun check
        """
        self.fail = fail
        self.run_check = run_check

        self.text = fail.msg
        self.margin = 5
        self.btn_h = 25
        self.btn_w = fail.button_width or 100

        _n_actions = len(fail.actions)
        self.btns_height = (
            self.btn_h*_n_actions +
            self.margin*(_n_actions + 1))

        super(SCUiFailItem, self).__init__(list_view=list_view, data=fail)

    def build_ui(self):
        """Build ui elements."""

        # Build main horiz layout
        self.h_lyt = QtWidgets.QHBoxLayout()
        self.h_lyt.setSpacing(self.margin)
        self.h_lyt.setContentsMargins(
            self.margin, self.margin, self.margin, self.margin)

        # Add text label
        self.label = qt.CLabel(self.text)
        self.label.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        self.label.setWordWrap(True)
        _n_actions = len(self.fail.actions)
        self.label.setFixedHeight(
            self.btn_h*_n_actions +
            self.margin*(_n_actions - 1))
        self.h_lyt.addWidget(self.label)

        # Build vert layout for buttons
        self.v_lyt = QtWidgets.QVBoxLayout()
        self.v_lyt.setSpacing(5)
        self.v_lyt.setContentsMargins(0, 0, 0, 0)

        # Add button list
        self.btns = []
        _catcher = error.get_catcher(parent=self.list_view, qt_safe=True)
        for _label, _action, _is_fix in self.fail.actions:
            _btn = QtWidgets.QPushButton(_label)
            _btn.setFixedSize(self.btn_w, self.btn_h)
            if _is_fix:
                _action = chain_fns(_action, self.run_check)
            _func = _catcher(_action)
            _btn.clicked.connect(_func)
            self.v_lyt.addWidget(_btn)
            self.btns.append(_btn)
        self.v_lyt.addStretch(0)
        self.h_lyt.addLayout(self.v_lyt)

        self.widget.setLayout(self.h_lyt)
        self.h_lyt.setStretch(0, 1)
        self.h_lyt.setStretch(1, 0)

    def redraw(self, widget_h=None):  # pylint: disable=arguments-differ,arguments-renamed
        """Redraw this item.

        Args:
            widget_h (int): force widget height (for debugging)
        """
        _font = self.label.font()
        _metrics = QtGui.QFontMetrics(_font)
        _cur_rect = self.label.geometry()
        _rect = _metrics.boundingRect(
            _cur_rect, Qt.AlignLeft | Qt.AlignTop | Qt.TextWordWrap, self.text)
        _text_h = _rect.height() + 5
        if widget_h:
            _widget_h = widget_h
        else:
            _widget_h = max(self.btns_height, _text_h)
        self._height = _widget_h

        super(SCUiFailItem, self).redraw()

        _item_w = self.list_view.get_draw_width()
        self.widget.setFixedSize(_item_w, _widget_h)
        self.label.setFixedHeight(_widget_h)
        if not self.btns:
            _label_w = _item_w - self.margin*2
        else:
            _label_w = _item_w - self.btn_w - self.margin*2
        self.label.setFixedSize(_label_w, _item_w)

        _item_h = _widget_h + self.margin*2
        _size_hint = qt.to_size(_item_w, _item_h)
        self.setSizeHint(_size_hint)
