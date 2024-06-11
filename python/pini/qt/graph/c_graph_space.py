"""Tools for managing a graph space container."""

# pylint: disable=too-many-public-methods,too-many-instance-attributes

import logging
import operator

from pini.utils import strftime, check_heart, HOME, File

from .. import wrapper, q_utils
from ..q_mgr import QtGui, QtCore, Qt

from . import c_graph_elem

_LOGGER = logging.getLogger(__name__)

_GRAPH_LINE_COL = wrapper.CColor('Grey')
_GRAPH_LINE_COL.setAlphaF(0.5)


class CGraphSpace(wrapper.CPixmapLabel, c_graph_elem.CGraphElemBase):
    """Represents a graph, a window into a pannable 2D space."""

    _prev_size = None
    _settings_file = None
    _window = None

    def __init__(
            self, parent, col='BottleGreen', legend='Graph Space'):
        """Constructor.

        Args:
            parent (QWidget): parent widget
            col (str): base colour
            legend (str): legend text (displayed in top left)
        """
        super(CGraphSpace, self).__init__(parent, col=col, margin=0)

        self.elems = []
        self.draw_callbacks = []
        self.legend = legend

        # Offset + zoom controls
        self.offset_p = wrapper.CVector2D()
        self.zoom = 1.0

        # Drag controls
        self.zoom_anchor_p = self.zoom_anchor_g = None
        self.offset_anchor_p = self.offset_target_p = None
        self.offset_p_start = None
        self.drag_button = self.drag_elem = None

    @property
    def window(self):
        """Obtain this space's parent window.

        Returns:
            (QWindow): window
        """
        if not self._window:
            _parent = self.parent()
            while _parent.parent():
                check_heart()
                # _LOGGER.info(' - PARENT %s', _parent)
                _parent = _parent.parent()
            self._window = _parent
        return self._window

    @property
    def settings_file(self):
        """Obtain settings file for this space.

        Returns:
            (File): settings file
        """
        _settings_name = type(self.window).__name__.strip('_')
        return self._settings_file or HOME.to_file(
            '.pini/GraphSpace/{}_{}.yml'.format(
                _settings_name, self.objectName()))

    def setup_shortcuts(self):
        """Apply shortcuts to the graph's window."""
        self.window.add_shortcut(
            's', self.save_settings, 'Save settings')
        self.window.add_shortcut(
            'f', self.frame_elems, 'Frame selected elements')
        self.window.add_shortcut(
            'r', self.reset_selected_elems, 'Reset selected elements')

    def add_draw_callback(self, callback):
        """Add a draw callback to this space.

        This will be execute on every redraw.

        Args:
            callback (fn): callback to execute
        """
        self.draw_callbacks.append(callback)

    def draw_pixmap(
            self, pix, markers=False, controls=True, grid=True,
            shortcuts=True):
        """Draw this space's pixmap.

        Args:
            pix (CPixmap): pixmap to draw on
            markers (bool): draw markers (drag marker overlays)
            controls (bool): draw controls in bottom left (offset/zoom data)
            grid (bool): draw background grid
            shortcuts (bool): list shortcuts in the bottom right
        """
        super(CGraphSpace, self).draw_pixmap(pix)

        # Draw background grid
        if grid:
            self._draw_grid(pix)

        # Draw elements
        _rect_p = pix.rect()
        _rect_g = self.p2g(_rect_p)
        for _elem in self.elems:
            if not _rect_g.intersects(_elem.rect_g):
                continue
            _elem.draw(pix=pix)

        # Execute draw callbacks
        for _callback in self.draw_callbacks:
            _callback(pix)

        # Draw overlays
        if markers:
            self._draw_markers(pix)
        if controls:
            self._draw_controls(pix)
        if shortcuts and self.window:
            self._draw_shortcuts(pix)

        if self.legend:
            pix.draw_text(self.legend, (10, 10))

    def _draw_markers(self, pix):
        """Draw offset/zoom markers.

        Args:
            pix (CPixmap): pixmap to draw on
        """
        if self.offset_anchor_p:
            pix.draw_dot(self.offset_anchor_p, col='Red', radius=10)
        if self.offset_target_p:
            pix.draw_dot(self.offset_target_p, col='Green', radius=10)
            pix.draw_line(self.offset_anchor_p, self.offset_target_p)
        if self.zoom_anchor_p:
            pix.draw_dot(
                self.zoom_anchor_p, col='Yellow', radius=self.g2p(10))
        if self.zoom_anchor_g:
            pix.draw_dot(
                self.g2p(self.zoom_anchor_g), col='Gold',
                radius=self.g2p(10))

    def _draw_controls(self, pix):
        """Draw offset/zoom controls data.

        Args:
            pix (CPixmap): pixmap to draw on
        """
        _text = 'offset=({:.02f}, {:.02f}) zoom={:.02f}'.format(
            self.offset_p.x(), self.offset_p.y(), self.zoom)
        pix.draw_text(
            _text, pix.rect().bottomLeft() + q_utils.to_p(10, -10),
            anchor='BL')

    def _draw_shortcuts(self, pix):
        """List keyboard shortcuts in bottom right of the graph.

        Args:
            pix (CPixmap): pixmap to draw on
        """
        _text = 'shortcuts:'
        _map = {Qt.Key_Escape: 'Esc'}
        for _key, (_, _label) in sorted(
                self.window.shortcuts.items(), key=str):
            _key = _map.get(_key, _key).capitalize()
            _text += '\n{}: {}'.format(_key, _label)
        pix.draw_text(
            _text, pix.rect().bottomRight() - q_utils.to_p(10, 10),
            anchor='BR')

    def _draw_grid(self, pix):
        """Draw background grid.

        Args:
            pix (CPixmap): pixmap to draw on
        """
        _rect_p = pix.rect()
        _rect_g = self.p2g(_rect_p)
        _LOGGER.log(9, 'DRAW GRID %s', _rect_g)

        # Draw vertical lines
        _x_plot_g = int(_rect_g.x()/100)*100 - 100
        _LOGGER.log(9, ' - X PLOT START %f', _x_plot_g)
        while _x_plot_g < _rect_g.right() + 100:
            check_heart()
            _top_g = q_utils.to_p(_x_plot_g, _rect_g.top())
            _bot_g = q_utils.to_p(_x_plot_g, _rect_g.bottom())
            pix.draw_line(
                self.g2p(_top_g), self.g2p(_bot_g), col=_GRAPH_LINE_COL)
            _x_plot_g += 100

        # Draw horizontal lines
        _y_plot_g = int(_rect_g.y()/100)*100 - 100
        _LOGGER.log(9, ' - Y PLOT START %f', _y_plot_g)
        while _y_plot_g < _rect_g.bottom() + 100:
            check_heart()
            _left_g = q_utils.to_p(_rect_g.left(), _y_plot_g)
            _right_g = q_utils.to_p(_rect_g.right(), _y_plot_g)
            pix.draw_line(
                self.g2p(_left_g), self.g2p(_right_g), col=_GRAPH_LINE_COL)
            _y_plot_g += 100

    def frame_elems(self, margin=20, draw_region=False, elems=None, anchor='C'):
        """Frame elements contained in this space.

        Args:
            margin (int): add margin (in game space)
            draw_region (bool): draw framing region overlay (for debugging)
            elems (CGBasicElem list): override elements to frame
            anchor (str): how to anchor framing
        """
        _LOGGER.debug('FRAME ELEMENTS %s', self)

        # Calculate framing rect
        _elems = elems or self.find_elems(selected=True) or self.find_elems()
        _f_rect_g = None
        for _elem in _elems:
            if not _f_rect_g:
                _f_rect_g = QtCore.QRectF(_elem.rect_g)
            else:
                _f_rect_g |= _elem.rect_g
        _f_rect_g = _f_rect_g.adjusted(-margin, -margin, margin, margin)
        _LOGGER.debug(' - FRAME RECT G %s', _f_rect_g)
        _f_rect_p = self.g2p(_f_rect_g)
        _LOGGER.debug(' - FRAME RECT P %s', _f_rect_p)

        # Draw framing region
        if draw_region:
            _col = wrapper.CColor('Yellow')
            _col.setAlphaF(0.5)
            _pix = self.redraw()
            _pix.draw_rect(
                pos=_f_rect_p.topLeft(), size=_f_rect_p.size(), col=_col,
                outline=None)
            self.setPixmap(_pix)
            return

        # Update zoom
        _anchor_p = _f_rect_p.center()
        _space_a = self.width() / self.height()
        _rect_a = _f_rect_p.width() / _f_rect_p.height()
        if _space_a > _rect_a:
            _zoom_mult = self.height() / _f_rect_p.height()
            _LOGGER.debug(' - MATCH HEIGHT')
        else:
            _zoom_mult = self.width() / _f_rect_p.width()
            _LOGGER.debug(
                ' - MATCH WIDTH %s %s', self.width(), _f_rect_p.width())
        _LOGGER.debug(' - ZOOM MULT %s', _zoom_mult)
        self._apply_zoom_change(anchor_p=_anchor_p, mult=_zoom_mult)

        # Update offset - to get this to frame centre horizontally we would
        # need to make the aspect of the frame rect match the space aspect
        _f_rect_p = self.g2p(_f_rect_g)
        if anchor == 'L':
            _space_p_left = wrapper.CVector2D(0, self.height()/2)
            _f_rect_p_left = wrapper.CVector2D(
                _f_rect_p.left(), _f_rect_p.center().y())
            _d_offset_p = _space_p_left - _f_rect_p_left
            _LOGGER.debug(
                ' - DELTA OFFSET %s -> %s = %s', _f_rect_p_left, _space_p_left,
                _d_offset_p)
        elif anchor == 'C':
            _space_p_ctr = wrapper.CVector2D(self.width()/2, self.height()/2)
            _f_rect_p_ctr = wrapper.CVector2D(_f_rect_p.center())
            _d_offset_p = _space_p_ctr - _f_rect_p_ctr
        else:
            raise ValueError(anchor)
        self.offset_p += _d_offset_p

        self.redraw()

    def clear_selection(self):
        """Clear current selection."""
        for _elem in self.find_elems():
            _elem.selected = False

    def select_elem(self, elem):
        """Select the given element.

        Args:
            elem (CGBasicElem): element to select
        """
        self.clear_selection()
        elem.selected = True
        self.redraw()

    def reset_selected_elems(self):
        """Reset selected elements."""
        _elems = self.find_elems(selected=True)
        _LOGGER.info('RESET ELEMS %s', _elems)
        for _elem in _elems:
            _elem.reset()
        self.redraw()

    def g2p(self, item):
        """Map the given item from graph to pixmap space.

        Args:
            item (QPointF|QRectF|QSizeF): object to map (in graph space)

        Returns:
            (QPointF|QRectF|QSizeF): object in pixmap space
        """
        return _graph_to_pixmap(
            item=item, offset=self.offset_p, zoom=self.zoom)

    def p2g(self, item):
        """Map the given item from pixmap to graph space.

        Args:
            item (QPointF|QRectF|QSizeF): object to map (in pixmap space)

        Returns:
            (QPointF|QRectF|QSizeF): object in graph space
        """
        return _pixmap_to_graph(
            item, offset=self.offset_p, zoom=self.zoom)

    def load_settings(self):
        """Load settings to elements in this space."""
        _LOGGER.info('LOAD SETTINGS %s', self.settings_file.path)
        _settings = self.settings_file.read_yml(catch=True)

        # Apply element settings
        _elem_settings = _settings.get('elements', {})
        _to_apply = []
        for _name, _setting in _elem_settings.items():
            _elem = self.find_elem(_name)
            if not _elem:
                _LOGGER.info(' - FAILED TO FIND %s', _name)
                continue
            if not _elem.saveable:
                continue
            _to_apply.append((_elem, _setting))
        for _elem, _setting in sorted(_to_apply):
            _LOGGER.debug(' - APPLY SETTING %s %s', _elem, _setting)
            _elem.set_settings(_setting)

        # Apply window settings
        _glob_settings = _settings.get('global', {})
        if 'offset' in _glob_settings:
            self.offset_p = wrapper.CVector2D(
                *_glob_settings.get('offset', (0, 0)))
        if 'zoom' in _glob_settings:
            self.zoom = _glob_settings['zoom']
        if 'selected' in _glob_settings:
            self.clear_selection()
            for _name in _glob_settings['selected']:
                _elem = self.find_elem(_name)
                _elem.selected = True

        self.redraw()
        _LOGGER.info(' - LOAD SETTINGS COMPLETE')

    def get_settings(self):
        """Obtain graph setting settings.

        Returns:
            (dict): graph settings
        """

        # Get global settings
        _sel_elems = self.find_elems(saveable=True, selected=True)
        _sel_names = [_elem.full_name for _elem in _sel_elems]
        _glob_settings = {
            'selected': _sel_names,
            'offset': list(self.offset_p.to_tuple()),
            'zoom': self.zoom}

        # Get element settings
        _elems_settings = {}
        for _elem in self.find_elems(saveable=True):
            _elem_settings = _elem.get_settings()
            if not _elem_settings:
                continue
            _elems_settings[_elem.full_name] = _elem_settings
            _LOGGER.debug(
                ' - READ SETTING %s %s %d', _elem.full_name, _elem_settings,
                bool(_elem_settings))

        _settings = {
            'global': _glob_settings,
            'elements': _elems_settings}

        return _settings

    def save_settings(self, bkp=False):
        """Save settings for elements in this space.

        Args:
            bkp (bool): save bkp on save settings

        Returns:
            (dict): settings that were saved
        """
        _LOGGER.info('SAVE SPACE SETTINGS %s', self.settings_file)
        _settings = self.get_settings()
        self.settings_file.write_yml(_settings, force=True)
        if bkp:
            self.settings_file.bkp()
        return _settings

    def set_settings_file(self, file_):
        """Set settings file for this graph.

        Args:
            file_ (str): path to settings file
        """
        self._settings_file = File(file_)
        assert self._settings_file.extn == 'yml'

    def mousePressEvent(self, event):
        """Triggered by mouse press.

        Args:
            event (QMouseEvent): triggered event
        """
        _event = event
        _pos_g = self.p2g(_event.pos())
        _LOGGER.info('MOUSE PRESS %s %s', event, strftime('%H%M%S'))
        _LOGGER.info(' - POS G %s', _pos_g)

        self.offset_anchor_p = self.offset_target_p = _event.pos()
        self.offset_p_start = self.offset_p
        self.drag_button = _event.button()

        # Check for elems accepting event - if the event isn't passed from a
        # higher level element, elements underneath don't recieve event
        self.drag_elem = None
        _click_elems = [
            _elem for _elem in self.find_elems()
            if _elem.visible and _elem.contains(_pos_g)]
        _click_elems.sort(key=operator.attrgetter('level'), reverse=True)

        # Pass click down through elements until one blocks it
        for _elem in _click_elems:
            _event = _elem.mousePressEvent(event=_event)
            _LOGGER.info(
                ' - PRESS IN ELEM %s level=%d event=%s %d', _elem,
                _elem.level, _elem.rect_g,
                _elem.rect_g.contains(_pos_g))
            if not _event:
                _LOGGER.info(' - EVENT NOT PASSED THROUGH')
                if _elem.draggable:
                    self.drag_elem = _elem
                break
            _elem.mouseReleaseEvent(event)

        _LOGGER.info(' - CLICK ELEMS %s', _click_elems)
        if event.button() == Qt.LeftButton and not _click_elems:
            self.clear_selection()
        _LOGGER.info(' - DRAG ELEM %s', self.drag_elem)

    def mouseMoveEvent(self, event):
        """Triggered by mouse move.

        Args:
            event (QMouseEvent): triggered event
        """
        _LOGGER.log(
            9, 'MOUSE MOVE %s %s %s', event, strftime('%H%M%S'),
            self.offset_anchor_p)

        if self.offset_anchor_p:
            self.offset_target_p = event.pos()
            _offs_vect_p = wrapper.CVector2D(
                self.offset_target_p - self.offset_anchor_p)

            # Apply offset to drag elements
            if self.drag_elem:
                _LOGGER.log(9, 'MOVE %s', self.drag_elem)
                self.drag_elem.mouseMoveEvent(event)

            # Apply offset to parent graph space
            elif self.drag_button == Qt.MiddleButton:
                self.offset_p = self.offset_p_start + _offs_vect_p
                self.offset_p = wrapper.CVector2D(self.offset_p)
                # self.update_t = time.time()

            self.redraw()

    def mouseReleaseEvent(self, event):
        """Triggered by mouse release.

        Args:
            event (QMouseEvent): triggered event
        """
        _LOGGER.info('MOUSE RELEASE %s %s', event, strftime('%H%M%S'))

        self.offset_anchor_p = self.offset_target_p = None
        if self.drag_elem:
            self.drag_elem.mouseReleaseEvent(event)
            self.drag_elem = None

        self.redraw()

    def mouseDoubleClickEvent(self, event):
        """Triggered by mouse double click.

        Args:
            event (QMouseEvent): triggered event
        """
        _LOGGER.info('MOUSE DOUBLE CLICK %s', event)

    def resizeEvent(self, event, apply_centering=False):
        """Triggered by resize.

        Args:
            event (QResizeEvent): triggered event
            apply_centering (bool): maintain centre point
        """
        _LOGGER.debug('RESIZE EVENT %s', event)

        super(CGraphSpace, self).resizeEvent(event)

        if apply_centering:
            _cur_size = self.size()
            if not self._prev_size or self._prev_size == _cur_size:
                self._prev_size = _cur_size
            else:
                _LOGGER.info(
                    ' - UPDATE SIZE %s -> %s', self._prev_size, _cur_size)
                _pre_ctr_p = q_utils.to_p(self._prev_size/2)
                _post_ctr_p = q_utils.to_p(_cur_size/2)
                self.offset_p += wrapper.CVector2D(_post_ctr_p - _pre_ctr_p)
                # self.update_t = time.time()
                self.redraw()
                self._prev_size = _cur_size

    def wheelEvent(self, event):
        """Triggered by mouse wheel move.

        Args:
            event (QEvent): triggered event
        """
        _LOGGER.debug('MOUSE WHEEL %s %s', event.delta(), event.pos())
        _mods = event.modifiers()
        _shift = event.modifiers() == Qt.ShiftModifier
        _LOGGER.debug(' - MODS %s %s', _mods, _shift)

        _mult = 1.2 if _shift else 1.1
        if event.delta() > 0:
            _mult = 1.0 / _mult

        self._apply_zoom_change(anchor_p=event.pos(), mult=_mult)

    def _apply_zoom_change(self, anchor_p, mult):
        """Apply a zoom change.

        At the event position, graph position and pixmap position should
        both remain constant.

        Args:
            anchor_p (CPointF): anchor point
            mult (float): zoom multiply
        """
        _LOGGER.debug('APPLY ZOOM CHANGE %s', mult)
        _LOGGER.debug(' - ZOOM ANCHOR P %s', anchor_p)

        self.zoom_anchor_p = q_utils.to_p(anchor_p, class_=wrapper.CPointF)
        self.zoom_anchor_g = self.p2g(self.zoom_anchor_p)
        _LOGGER.debug(
            ' - ZOOM ANCHOR G (A) %s offs=%s zoom=%s', self.zoom_anchor_g,
            self.offset_p, self.zoom)

        _start_zoom = self.zoom
        self.zoom *= mult
        _LOGGER.debug(' - ZOOM %s -> %s', _start_zoom, self.zoom)
        _end_g = self.p2g(self.zoom_anchor_p)
        _LOGGER.debug(' - PG CHANGE %s -> %s', self.zoom_anchor_g, _end_g)
        _vect_g = wrapper.CVector2D(_end_g - self.zoom_anchor_g)
        _vect_p = self.g2p(_vect_g)
        _LOGGER.debug(' - VECT %s -> %s', _vect_g, _vect_p)

        self.offset_p += _vect_p
        self.offset_p = wrapper.CVector2D(self.offset_p)
        _LOGGER.debug(' - ZOOM ANCHOR G (B) %s', self.p2g(self.zoom_anchor_p))
        _LOGGER.debug(' - OFFSET P %s', self.offset_p)

        # self.update_t = time.time()

        self.redraw()


def _graph_to_pixmap(item, offset, zoom):
    """Map the given item from graph to pixmap space.

    Args:
        item (QPointF|QRectF|QSizeF): object to map (in graph space)
        offset (QVector2D): offset vector
        zoom (float): zoom

    Returns:
        (QPointF|QRectF|QSizeF): object in pixmap space
    """
    _offs_p = wrapper.CVector2D(offset)

    if isinstance(item, (QtCore.QPoint, QtCore.QPointF)):
        _pt_g = wrapper.CPointF(item)
        _LOGGER.log(9, ' - GAME TO PIXMAP %s o=%s z=%s', _pt_g, _offs_p, zoom)
        _vect_p = (wrapper.CVector2D(_pt_g) * zoom) + _offs_p
        _pt_p = wrapper.CPointF(_vect_p.x(), _vect_p.y())
        _LOGGER.log(9, '   - RESULT %s', _pt_p)
        return _pt_p

    if isinstance(item, (float, int)):
        return zoom * item

    if isinstance(item, QtGui.QVector2D):
        return wrapper.CVector2D(item * zoom)

    if isinstance(item, (QtCore.QSize, QtCore.QSizeF)):
        return wrapper.CSizeF(item * zoom)

    if isinstance(item, QtCore.QRectF):
        _pos = _graph_to_pixmap(item.topLeft(), offset=offset, zoom=zoom)
        _size = _graph_to_pixmap(item.size(), offset=offset, zoom=zoom)
        return QtCore.QRectF(_pos, _size)

    raise NotImplementedError(item)


def _pixmap_to_graph(item, offset, zoom):
    """Map the given item from pixmap to graph space.

    Args:
        item (QPointF|QRectF|QSizeF): object to map (in pixmap space)
        offset (QVector2D): offset vector
        zoom (float): zoom

    Returns:
        (QPointF|QRectF|QSizeF): object in graph space
    """
    _offs_p = wrapper.CVector2D(offset)

    if isinstance(item, (QtCore.QPoint, QtCore.QPointF)):
        _pt_p = wrapper.CPointF(item)
        _LOGGER.log(9, ' - PIXMAP TO GAME %s o=%s z=%s', _pt_p, _offs_p, zoom)
        _val = (_pt_p - _offs_p) / zoom
        _LOGGER.log(9, '   - RESULT %s', _val)
        return wrapper.CPointF(_val)

    if isinstance(item, (float, int)):
        return item / zoom

    if isinstance(item, QtGui.QVector2D):
        return wrapper.CVector2D(item / zoom)

    if isinstance(item, (QtCore.QSize, QtCore.QSizeF)):
        return wrapper.CSizeF(item / zoom)

    if isinstance(item, (QtCore.QRectF, QtCore.QRect)):
        _pos = _pixmap_to_graph(item.topLeft(), offset=offset, zoom=zoom)
        _size = _pixmap_to_graph(item.size(), offset=offset, zoom=zoom)
        return QtCore.QRectF(_pos, _size)

    raise NotImplementedError(item)
