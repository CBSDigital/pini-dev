"""Tools for managing graph nodes."""

import logging

from pini.utils import single

from ..q_mgr import QtCore, QtWidgets, QtGui, Qt
from .. import q_utils, wrapper

_LOGGER = logging.getLogger(__name__)


class PNGNode(QtWidgets.QGraphicsItem, QtCore.QObject):
    """Base class and lip service graph node.

    The QObject parent is needed to allow signals to be added.
    """

    pos_changed = QtCore.Signal(QtWidgets.QGraphicsItem)

    def __init__(
            self, name, scene, rect, col='Red', selected_col=None,
            moveable=False, selectable=False, bevel=20, label=None,
            text_size=32, text_align=None, pen=None, parent=None,
            x_min=None, x_max=None, y_min=None, y_max=None):
        """Constructor.

        Args:
            name (str): node name
            scene (QGraphicsScene): parent scene
            rect (QRect): node region
            col (str): node colour
            selected_col (str): override colour on selection
            moveable (bool|str): whether node is moveable
                False - not moveable
                True - fully moveable
                h - allow horizonal movement
                v - allow vertical movement
            selectable (bool): whether node is selecteble
            bevel (int): node bevel
            label (str): node label
            text_size (int): node text size
            text_align (AlignmentFlag): alignment
            pen (QPen): pen for drawing outline
            parent (QGraphicsItem): parent node
            x_min (int): min x limit
            x_max (int): max x limit
            y_min (int): min y limit
            y_max (int): max y limit
        """
        super().__init__(parent=parent)
        QtCore.QObject.__init__(self)

        self.name = name
        self.label = label

        self.local_rect = rect
        self.local_p_0 = q_utils.to_p(0, 0)
        self.rect_0 = self.rect

        self.bevel = bevel
        self.text_size = text_size
        self.text_align = text_align
        self.col = q_utils.to_col(col) if col else None
        self.pen = q_utils.to_pen(pen) or Qt.NoPen

        self.x_min = x_min
        self.x_max = x_max
        self.y_min = y_min
        self.y_max = y_max

        if selected_col:
            self.selected_col = q_utils.to_col(selected_col)
        elif self.col:
            self.selected_col = wrapper.CColor(*self.col.to_tuple(int))
            _hue, _sat, _val, _alpha = self.selected_col.getHsvF()
            _hue = _hue + 0.2 % 1
            _alpha = self.col.alphaF()
            self.selected_col.setHsvF(_hue, _sat, _val, _alpha)

        assert moveable in (False, True, 'h', 'v')
        self.moveable = moveable
        self.setFlag(
            QtWidgets.QGraphicsItem.ItemIsMovable, bool(moveable))
        self.setFlag(
            QtWidgets.QGraphicsItem.ItemSendsGeometryChanges, bool(moveable))
        self.setFlag(
            QtWidgets.QGraphicsItem.ItemIsSelectable, selectable)

        scene.addItem(self)

    @property
    def rect(self):
        """Obtain current node region in scene space.

        Returns:
            (QRect): scene rect
        """
        return self.sceneBoundingRect()

    @property
    def view(self):
        """Obtain parent view for this node.

        Returns:
            (QGraphicsView): view
        """
        return single(self.scene().views())

    def boundingRect(self):
        """Obtain local bounding rect.

        Returns:
            (QRect): bounding region (required for graphics view)
        """
        return self.local_rect

    def itemChange(self, change, value):
        """Triggered by item change.

        Args:
            change (GraphicsItemChange): change that occurred
            value (any): change value

        Returns:
            (any): value
        """
        _val = value
        _LOGGER.debug(
            'ITEM CHANGE %s %s %s', self, change.name.decode(), _val)

        # Apply axis locks
        if change == QtWidgets.QGraphicsItem.ItemPositionChange:

            # Apply axis limits
            if self.moveable is True:
                pass
            elif self.moveable == 'h':
                _val.setY(self.local_p_0.y())
            elif self.moveable == 'v':
                _val.setX(self.local_p_0.x())
            else:
                raise ValueError(self.moveable)

            # Apply limits
            _val = self._apply_move_limits(_val)

        # Apply axis locks
        if change == QtWidgets.QGraphicsItem.ItemPositionHasChanged:
            self.pos_changed.emit(self)

        return super().itemChange(change, _val)

    def _apply_move_limits(self, value):  # pylint: disable=too-many-branches
        """Apply movement limits.

        Args:
            value (QPoint): position to update

        Returns:
            (QPoint): position with limits applied
        """
        _val = value
        _parent = self.parentItem()
        _LOGGER.debug(' - PARENT %s', _parent)

        if self.x_min is not None:
            _x_offs = self.rect_0.left()
            if _parent:
                _x_min = self.x_min
            else:
                _x_min = self.x_min - _x_offs
            _LOGGER.debug(' - APPLY MIN min=%s val=%s', _x_min, _val.x())
            if _val.x() < _x_min:
                _val.setX(_x_min)
                _LOGGER.debug(' - APPLY X MIN LIMIT')

        if self.x_max is not None:
            _x_offs = self.rect_0.left()
            if _parent:
                _x_max = self.x_max - self.rect_0.width()
            else:
                _x_max = self.x_max - _x_offs - self.rect_0.width()
            if _val.x() > _x_max:
                _val.setX(_x_max)
                _LOGGER.debug(' - APPLY X MAX LIMIT')

        if self.y_min is not None:
            _y_offs = self.rect_0.top()
            if _parent:
                _y_min = self.y_min
            else:
                _y_min = self.y_min - _y_offs
            if _val.y() < _y_min:
                _val.setY(_y_min)
                _LOGGER.debug(' - APPLY Y MIN LIMIT')

        if self.y_max is not None:
            _y_offs = self.rect_0.left()
            if _parent:
                _y_max = self.y_max - self.rect_0.height()
            else:
                _y_max = self.y_max - _y_offs - self.rect_0.height()
            if _val.y() > _y_max:
                _val.setY(_y_max)
                _LOGGER.debug(' - APPLY Y MAX LIMIT')

        return _val

    def paint(self, painter, option, widget):  # pylint: disable=unused-argument
        """Paint event.

        Args:
            painter (QPainter): painter
            option (QStyleOptionGraphicsItem): option
            widget (QWidget): parent widget
        """
        painter.setPen(self.pen)

        if self.col:
            if not self.isSelected():
                _col = self.col
            else:
                _col = self.selected_col
            painter.setBrush(_col)
            painter.drawRoundedRect(self.local_rect, self.bevel, self.bevel)

        if self.label:
            painter.setFont(QtGui.QFont("Arial", self.text_size))
            painter.setPen(QtGui.QColor('Black'))
            _align = self.text_align or Qt.AlignCenter
            painter.drawText(self.local_rect, _align, self.label)

    def __repr__(self):
        _type = type(self).__name__.strip('_')
        _name_str = ''
        if self.name:
            _name_str = f':{self.name}'
        return f'<{_type}{_name_str}>'
