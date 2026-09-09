"""Tools for managing the substance painter pini helper."""

# pylint: disable=abstract-method,too-many-ancestors

import logging

from .. import ph_window

_SPAINTER_FIX_QSS = '''
QListView, QTreeView, QTableView {
    background-color: #191919;
    alternate-background-color: #232323;
}
QLineEdit, QTextEdit, QPlainTextEdit, QComboBox {
    background-color: #191919;
}
QPushButton, QToolButton {
    min-width: 0px;
    min-height: 0px;
    padding: 1px;
}
'''

_LOGGER = logging.getLogger(__name__)


class SPainterPiniHelper(ph_window.PiniHelper):
    """Pini helper dialog for substance painter."""

    def __init__(self, *args, **kwargs):
        """Constructor."""
        super().__init__(*args, **kwargs)
        self.setStyleSheet(_SPAINTER_FIX_QSS)
