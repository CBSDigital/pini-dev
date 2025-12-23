"""Tools for managing the rectangular node."""

import logging

from pini.utils import single

from ..q_mgr import QtCore, QtWidgets, QtGui, Qt
from .. import q_utils

_LOGGER = logging.getLogger(__name__)


class PNGNode(QtWidgets.QGraphicsRectItem, QtCore.QObject):
    """Displays a coloured rectangle on a graph."""

    pos_changed = QtCore.Signal(QtWidgets.QGraphicsItem)

    def __init__(
            self, name, scene, rect, col='Red',
            # selected_col=None,
            moveable=False, selectable=False, bevel=20, label=None,
            text_size=20, text_align=None, pen=None, parent=None,
            limit=None, callback=None):
        """Constructor.

        Args:
            name (str): node name
            scene (QGraphicsScene): parent scene
            rect (QRect): node region
            col (str): node colour
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
            limit (QRect): movement bound limits
            callback (fn): callback on node clicked
        """
        _LOGGER.debug('INIT PNGNode parent=%s', parent)
        super().__init__(parent=parent)
        # assert not parent
        QtCore.QObject.__init__(self)

        self.setRect(rect)

        self.name = name
        self.label = label
        self.callback = callback

        # self.local_rect = rect
        # self.local_p_0 = q_utils.to_p(0, 0)
        self.rect_0 = self.rect()

        self.bevel = bevel
        self.text_size = text_size
        self.text_align = text_align
        # self.col = q_utils.to_col(col) if col else None
        self.setPen(q_utils.to_pen(pen) or Qt.NoPen)
        if col:
            self.set_col(col)

        self.limit = limit
        if limit and not isinstance(limit, (QtCore.QRect, QtCore.QRectF)):
            raise TypeError(limit)

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
    def view(self):
        """Obtain parent view for this node.

        Returns:
            (QGraphicsView): view
        """
        return single(self.scene().views())

    def set_col(self, col):
        """Set colour of this node.

        Args:
            col (str|QColor): colour to apply
        """
        self.setBrush(QtGui.QBrush(q_utils.to_col(col)))

    def itemChange(self, change, value):
        """Triggered by item change.

        Args:
            change (GraphicsItemChange): change that occurred
            value (any): change value

        Returns:
            (any): value
        """
        _val = value
        _name = change.name
        if not isinstance(_name, str):
            _name = _name.decode()  # For PySide2
        _LOGGER.debug(
            'ITEM CHANGE %s %s %s', self, _name, _val)

        # Apply axis locks
        if change == QtWidgets.QGraphicsItem.ItemPositionChange:

            # Apply axis limit
            if self.moveable is True:
                pass
            elif self.moveable == 'h':
                _val.setY(self.local_p_0.y())
            elif self.moveable == 'v':
                _val.setX(self.local_p_0.x())
            else:
                raise ValueError(self.moveable)

            # Apply limit
            if self.limit:
                _val = self._apply_move_limit(_val)

        # Apply axis locks
        if change == QtWidgets.QGraphicsItem.ItemPositionHasChanged:
            self.pos_changed.emit(self)

        return super().itemChange(change, _val)

    def _apply_move_limit(self, value):  # pylint: disable=too-many-branches
        """Apply movement limit.

        Args:
            value (QPoint): position to update

        Returns:
            (QPoint): position with limit applied
        """
        _val = value
        _parent = self.parentItem()
        _LOGGER.debug(' - PARENT %s', _parent)

        # Apply left
        _x_offs = self.rect().left()
        if _parent:
            _x_min = self.limit.left()
        else:
            _x_min = self.limit.left() - _x_offs
        _LOGGER.debug(' - APPLY MIN min=%s val=%s', _x_min, _val.x())
        if _val.x() < _x_min:
            _val.setX(_x_min)
            _LOGGER.debug(' - APPLY X MIN LIMIT')

        # Apply right limit
        _x_offs = self.rect().left()
        if _parent:
            _x_max = self.limit.right() - self.rect().width()
        else:
            _x_max = self.limit.right() - _x_offs - self.rect().width()
        if _val.x() > _x_max:
            _val.setX(_x_max)
            _LOGGER.debug(' - APPLY X MAX LIMIT')

        # Apply top limit
        _y_offs = self.rect().top()
        if _parent:
            _y_min = self.limit.top()
        else:
            _y_min = self.limit.top() - _y_offs
        if _val.y() < _y_min:
            _val.setY(_y_min)
            _LOGGER.debug(' - APPLY Y MIN LIMIT')

        # Apply bottom limit
        _y_offs = self.rect().top()
        if _parent:
            _y_max = self.limit.bottom() - self.rect().height()
        else:
            _y_max = self.limit.bottom() - _y_offs - self.rect().height()
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
        painter.setBrush(self.brush())
        painter.setPen(self.pen())
        painter.drawRoundedRect(self.rect(), self.bevel, self.bevel)

        if self.label:
            painter.setFont(QtGui.QFont("Arial", self.text_size))
            painter.setPen(QtGui.QColor('Black'))
            _align = self.text_align or Qt.AlignCenter
            painter.drawText(self.rect(), _align, self.label)

    def mousePressEvent(self, event):
        """Mouse press event.

        Args:
            event (QEvent): event
        """
        if self.callback:
            from pini.tools import error
            _catcher = error.get_catcher(qt_safe=True)
            _callback = _catcher(self.callback)
            _callback()
        else:
            super().mousePressEvent(event)

    def __repr__(self):
        _type = type(self).__name__.strip('_')
        _name_str = ''
        if self.name:
            _name_str = f':{self.name}'
        return f'<{_type}{_name_str}>'
