"""Tools for managing the icon button.."""

import logging

from ...q_mgr import QtWidgets
from . import qw_base_widget
from ... import q_utils

_LOGGER = logging.getLogger(__name__)


class CIconButton(QtWidgets.QPushButton, qw_base_widget.CBaseWidget):
    """Adds functionality to QPushButton object."""

    def __init__(self, parent, icon, name=None):
        """Constructor.

        Args:
            parent (QWidget): parent widget
            icon (str): path to widget icon
            name (str): widget name
        """
        super().__init__(parent)

        self.setFixedWidth(20)
        self.setFixedHeight(20)
        self.setIconSize(q_utils.to_size(20))
        self.setIcon(q_utils.to_icon(icon))
        self.setFlat(True)

        if name:
            self.setObjectName(name)
