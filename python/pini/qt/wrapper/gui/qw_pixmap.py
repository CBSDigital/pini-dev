"""Tools for adding functionality to QPixmap."""

import logging
import os
import sys

from pini.utils import (
    File, TMP_PATH, abs_path, basic_repr, error_on_file_system_disabled,
    single)

from .qw_painter import CPainter
from ...q_mgr import QtGui, Qt, QtCore

_LOGGER = logging.getLogger(__name__)
TEST_IMG = TMP_PATH+'/test.jpg'

# Set pixmap formats
if sys.version_info.major == 3:
    PIXMAP_EXTNS = [
        str(_item, encoding='utf-8')
        for _item in QtGui.QImageWriter.supportedImageFormats()]
elif sys.version_info.major == 2:
    PIXMAP_EXTNS = [
        'bmp', 'cur', 'icns', 'ico', 'jpeg', 'jpg', 'pbm', 'pgm', 'png', 'ppm',
        'tif', 'tiff', 'wbmp', 'webp', 'xbm', 'xpm']
else:
    raise NotImplementedError


class CPixmap(QtGui.QPixmap):
    """Wrapper for QPixmap."""

    def __init__(self, *args):
        """Constructor."""
        _args = list(args)
        if len(_args) == 1 and isinstance(_args[0], File):
            _args[0] = _args[0].path
        if len(_args) == 1 and isinstance(_args[0], str):
            error_on_file_system_disabled(path=_args[0])

        super(CPixmap, self).__init__(*_args)

    def aspect(self):
        """Obtain aspect ratio for this pixmap.

        Returns:
            (float): width/height ratio
        """
        return float(self.width())/self.height()

    def center(self):
        """Obtain centre point of this pixmap.

        Returns:
            (QPoint): centre
        """
        return self.rect().center()

    def crop(self, top=0, bottom=0, left=0, right=0):
        """Apply crop to this pixmap.

        Args:
            top (int): crop pixels from top
            bottom (int): crop pixels from bottom
            left (int): crop pixels from left
            right (int): crop pixels from right

        Returns:
            (QPixmap): cropped pixmap
        """
        from pini import qt
        _pos = qt.to_p(left, top)
        _size = qt.to_size(
            self.width() - right - left,
            self.height() - bottom - top)
        _rect = qt.to_rect(pos=_pos, size=_size)
        return qt.to_pixmap(self.copy(_rect))

    def draw_dot(self, pos, col='Black', radius=1.0, outline=None,
                 anchor='C'):
        """Draw a circular dot on this pixmap.

        Args:
            pos (QPoint): dot centre
            col (QColor): dot colour
            radius (float): dot radius
            outline (QPen): dot outline (default is None)
            anchor (str): draw anchor for dot rect

        Returns:
            (QRect): draw rect
        """
        from pini import qt

        _pos = qt.to_p(pos)
        if anchor != 'C':
            _pos = _pos + qt.to_p(1, 1)
            _rect = qt.to_rect(pos=_pos, size=int(radius*2), anchor=anchor)
            _pos = _rect.center()
        _col = qt.to_col(col)
        _brush = QtGui.QBrush(_col)

        # Set outline
        if not outline:
            _pen = QtGui.QPen(_col)
            _pen.setStyle(Qt.NoPen)
        else:
            raise NotImplementedError(outline)

        _pnt = qt.CPainter()
        _pnt.begin(self)
        _pnt.setBrush(_brush)
        _pnt.setPen(_pen)
        _pnt.drawEllipse(
            _pos.x()-radius, _pos.y()-radius, radius*2, radius*2)
        _pnt.end()

        return qt.to_rect(pos=_pos, size=int(radius*2), anchor='C')

    def draw_line(self, point_a, point_b, col='Black', thickness=None,
                  pen=None):
        """Draw a line on this pixmap.

        Args:
            point_a (QPoint): start point
            point_b (QPoint): end point
            col (QColor): line colour
            thickness (float): override line thickness
            pen (QPen): override pen
        """
        from pini import qt

        _pt_a = qt.to_p(point_a)
        _pt_b = qt.to_p(point_b)
        _col = qt.to_col(col)

        if pen:
            _pen = pen
        else:
            _pen = QtGui.QPen(_col)
            if thickness:
                _pen.setWidthF(thickness)
            _pen.setCapStyle(Qt.RoundCap)
            _pen.setJoinStyle(Qt.RoundJoin)

        _pnt = qt.CPainter()
        _pnt.begin(self)
        _pnt.setPen(_pen)
        _pnt.drawLine(_pt_a.x(), _pt_a.y(), _pt_b.x(), _pt_b.y())
        _pnt.end()

    def draw_overlay(
            self, pix, pos=None, anchor='TL', size=None, rotate=None,
            opacity=None):
        """Draw an image overlay on this pixmap.

        Args:
            pix (QPixmap): pixmap to apply
            pos (QPoint): draw position
            anchor (str): draw anchor
            size (QSize): apply image resize
            rotate (float): apply rotation in degrees
            opacity (float): apply opacity to overlay (in range 0-1)

        Returns:
            (QRect): draw region
        """
        from pini import qt

        _pix = qt.to_pixmap(pix)
        _size = qt.to_size(size) if size else _pix.size()
        _pos = qt.to_p(pos) if pos else QtCore.QPoint()
        _rect = qt.to_rect(pos=_pos, size=_size, anchor=anchor)
        if size:
            _pix = _pix.resize(_rect.size())

        _pnt = qt.CPainter()
        _pnt.begin(self)
        if opacity is not None:
            _pnt.setOpacity(opacity)
        if rotate is not None:
            _pnt.setRenderHint(_pnt.SmoothPixmapTransform)
            _rect = _pnt.apply_rotate(rect=_rect, rotate=rotate, anchor=anchor)
        _pnt.drawPixmap(_rect.x(), _rect.y(), _pix)
        _pnt.end()

        return _rect

    def draw_path(self, pts, col='black', thickness=None, pen=None):
        """Draw path (a series of lines) on this pixmap.

        Args:
            pts (QPoint list): points in line
            col (QColor): line colour
            thickness (float): line thickness
            pen (QPen): override pen
        """
        from pini import qt

        # Set pen
        if pen:
            _pen = pen
        else:
            _col = qt.to_col(col)
            _pen = QtGui.QPen(_col)
            _pen.setCapStyle(Qt.RoundCap)
            if thickness:
                _pen.setWidthF(thickness)

        _brush = QtGui.QBrush()
        _brush.setStyle(Qt.NoBrush)

        _pts = pts

        # Build path
        _path = QtGui.QPainterPath()
        _path.moveTo(qt.to_p(_pts[0]))
        for _pt in _pts[1:]:
            _path.lineTo(qt.to_p(_pt))

        _pnt = qt.CPainter()
        _pnt.begin(self)
        _pnt.setPen(_pen)
        _pnt.setBrush(_brush)
        _pnt.drawPath(_path)
        _pnt.end()

    def draw_polygon(self, pts, col='White', outline='Black', thickness=1.0,
                     pen=None):
        """Draw a polygon on this pixmap.

        Args:
            pts (QPoint list): points in polygon
            col (QColor): fill colour
            outline (QColor): outline colour
            thickness (float): outline thickness
            pen (QPen): outline pen

        Returns:
            (QRect): bounding rectangle
        """
        from pini import qt

        if pen:
            _pen = pen
        elif outline:
            _pen = QtGui.QPen(outline)
            _pen.setCapStyle(Qt.RoundCap)
            if thickness:
                _pen.setWidthF(thickness)
        else:
            _pen = QtGui.QPen()
            _pen.setStyle(Qt.NoPen)

        _col = qt.to_col(col)
        _brush = QtGui.QBrush(_col)

        # Build polygon
        _poly = QtGui.QPolygonF()
        for _pt in pts:
            _pt = qt.to_p(_pt)
            _poly.append(_pt)

        _pnt = qt.CPainter()
        _pnt.begin(self)
        _pnt.setBrush(_brush)
        _pnt.setPen(_pen)
        _pnt.drawPolygon(_poly)
        _pnt.end()

        return _poly.boundingRect()

    def draw_rect(
            self, pos=(0, 0), size=None, col='White', outline='Black',
            anchor='TL', rect=None, operation=None):
        """Draw rectangle on this pixmap.

        Args:
            pos (QPoint): rect position
            size (QSize): rect size
            col (QColor): rect fill colour
            outline (QColor): rect outline colour
            anchor (str): rect anchor
            rect (QRect): rect region (overrides pos/size args)
            operation (str): compositing operation

        Returns:
            (QRect): draw region
        """
        from pini import qt

        _pos = qt.to_p(pos)
        _col = qt.to_col(col)
        _brush = QtGui.QBrush(_col)
        if rect:
            _rect = rect
        else:
            _rect = qt.to_rect(pos=_pos, size=size, anchor=anchor)

        # Set outline
        if outline:
            _pen = QtGui.QPen(outline)
        else:
            _pen = QtGui.QPen()
            _pen.setStyle(Qt.NoPen)

        _pnt = qt.CPainter()
        _pnt.begin(self)
        _pnt.setPen(_pen)
        _pnt.setBrush(_brush)
        if operation:
            _mode = getattr(_pnt, 'CompositionMode_'+operation)
            _pnt.setCompositionMode(_mode)
        _pnt.drawRect(_rect)
        _pnt.end()

        return _rect

    def draw_rounded_overlay(self, pix, pos=(0, 0), bevel=5, anchor='TL'):
        """Draw an overlay with rounded corners.

        Args:
            pix (QPixmap|str): pixmap or path to overlay import
            pos (QPoint): position
            bevel (int): rounding radius in pixels
            anchor (str): anchor for overlay
        """
        from pini import qt
        _base = pix
        _pos = qt.to_p(pos)

        # Prepare overlay - needs to be drawn at origin
        _over = CPixmap(_base.size())
        _over.fill('Transparent')
        _over.draw_rounded_rect(
            col=_base, outline=None, size=_base.size(), bevel=bevel)

        self.draw_overlay(_over, pos=pos, anchor=anchor)

    def draw_rounded_rect(
            self, pos=(0, 0), size=None, col='White', outline='Black',
            anchor='TL', rect=None, bevel=5, brush=None):
        """Draw rectangle on this pixmap.

        Args:
            pos (QPoint): rect position
            size (QSize): rect size
            col (QColor|QPixmap): rect fill colour/pixmap - if a pixmap
                is passed then drawing starts at the origin, which can
                be undesirable
            outline (QColor): rect outline colour
            anchor (str): rect anchor
            rect (QRect): rect region (overrides pos/size args)
            bevel (int): rounding radius in pixels
            brush (QBrush): override fill brush

        Returns:
            (QRect): draw region
        """
        from pini import qt

        # Determine rect
        _pos = qt.to_p(pos)
        if rect:
            _rect = rect
        else:
            _rect = qt.to_rect(pos=_pos, size=size, anchor=anchor)

        # Determine colour
        _col = col
        if not isinstance(_col, QtGui.QPixmap):
            _col = qt.to_col(_col)
        _brush = brush or QtGui.QBrush(_col)

        # Set outline
        if outline:
            _pen = QtGui.QPen(outline)
        else:
            _pen = QtGui.QPen()
            _pen.setStyle(Qt.NoPen)

        _pnt = qt.CPainter()
        _pnt.begin(self)
        _pnt.setPen(_pen)
        _pnt.setBrush(_brush)
        _pnt.drawRoundedRect(_rect, bevel, bevel)
        _pnt.end()

        return _rect

    def draw_text(
            self, text, pos=(0, 0), anchor='TL', col='Black', font=None,  # pylint: disable=unused-argument
            size=None, line_h=None, rotate=0.0, rect=None):  # pylint: disable=unused-argument
        """Add text to pixmap.

        Args:
            text (str): text to add
            pos (tuple|QPoint): text position
            anchor (str): text anchor
            col (str|QColor): text colour
            font (QFont): text font
            size (int): font size
            line_h (int): override line height (draws each line separately)
            rotate (float): apply angle rotation (in degrees clockwise)
            rect (QRect): draw text wrapped in region (overrides pos arg)
        """
        _kwargs = locals()
        del _kwargs['self']

        _pnt = CPainter()
        _pnt.begin(self)
        _result = _pnt.draw_text(**_kwargs)
        _pnt.end()

        return _result

    def fill(self, col):
        """Fill this pixmap with the given colour.

        Args:
            col (QColor): colour to apply
        """
        from pini import qt
        _col = qt.to_col(col)
        super(CPixmap, self).fill(_col)

    def resize(self, *args, **kwargs):
        """Resize this image.

        If only height or width is passed, aspect is maintained.

        Size outputs (for aspect 2):
         - resize(10) -> (10, 5)
         - resize(height=10) -> (20, 5)
         - resize(10, 20) -> (10, 20)
         - resize([10, 20]) -> (10, 20)

        Returns:
            (QPixmap): resized image
        """
        _arg = single(args, catch=True)
        _width = kwargs.pop('width', None)
        _height = kwargs.pop('height', None)

        if _width:
            _height = _width / self.aspect()
        elif _height:
            _width = _height * self.aspect()
        else:
            assert not _height and not _width
            if isinstance(_arg, (int, float)):
                _width = _arg
                _height = _arg
            elif isinstance(_arg, (QtCore.QSize, QtCore.QSizeF)):
                _width = _arg.width()
                _height = _arg.height()
            elif isinstance(_arg, (tuple, list)) and len(_arg) == 2:
                _width, _height = _arg
            elif len(args) == 2:
                _width, _height = args
            else:
                raise ValueError(args, kwargs)

        # Use QImage for better scaling algorithm
        _LOGGER.debug(' - WIDTH/HEIGHT %s/%s', _width, _height)
        _img = self.toImage()
        _img = _img.scaled(
            _width, _height, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
        _pix = QtGui.QPixmap.fromImage(_img)

        return CPixmap(_pix)

    def rotate(self, degrees):
        """Apply rotation to this pixmap.

        Args:
            degrees (str): rotation in degrees

        Returns:
            (CPixmap): updated pixmap
        """
        _tfm = QtGui.QTransform()
        _tfm.rotate(degrees)
        return CPixmap(self.transformed(_tfm))

    def save_as(self, file_, force=False, quality=100, verbose=1):
        """Save this image to disk.

        Args:
            file_ (str): path to save to
            force (bool): overwrite with no warning dialog
            quality (int): file quality
                100 - maximum quality
                -1 - use system default quality
            verbose (int): print process data
        """
        error_on_file_system_disabled()
        assert self.width() and self.height()

        _file = File(file_)
        _fmt = {}.get(_file.extn, _file.extn.upper())
        if verbose:
            _LOGGER.info("SAVING %s %s", _file.path, _fmt)
        if _file.exists():
            if not force:
                from pini import qt
                _result = qt.yes_no_cancel(
                    'Overwrite existing image?\n\n'+_file.path)
                if _result == 'No':
                    return None
            os.remove(_file.path)
        _file.to_dir().mkdir()

        self.save(abs_path(_file.path, win=os.name == 'nt'),
                  format=_fmt, quality=quality)
        assert _file.exists()

        return _file

    def save_test(self, file_=None, extn='jpg'):
        """Save image to test file.

        Args:
            file_ (str): override test file path
            extn (str): text file extension

        Returns:
            (File): path to test file
        """
        if file_:
            self.save_as(file_, force=True)
            return file_
        _test_img = File(TEST_IMG).apply_extn(extn)
        self.save_as(_test_img.path, force=True)
        _LOGGER.info('SAVED TEST %s', _test_img.path)
        return _test_img

    def to_grayscale(self):
        """Convert this pixmap to grayscale.

        Returns:
            (CPixmap): updated pixmap
        """
        from pini import qt

        _img = self.toImage()
        if qt.LIB == 'PySide':
            _img = _img.convertToFormat(QtGui.QImage.Format_MonoLSB)
        else:
            _img = _img.convertToFormat(QtGui.QImage.Format_Grayscale8)
        _pix = CPixmap(QtGui.QPixmap.fromImage(_img))
        _pix.setMask(self.mask())
        return _pix

    def whiten(self, factor):
        """Whiten this pixmap.

        Args:
            factor (float): whiteness factor - 1.0 means fully white

        Returns:
            (CPixmap): whitened pixmap
        """
        from pini import qt

        _white = qt.CColor('White')
        _white.setAlphaF(factor)

        _tmp = CPixmap(self.size())
        _tmp.fill(_white)
        if self.hasAlpha():
            _tmp.setMask(self.mask())

        self.draw_overlay(_tmp)

        return self

    def __repr__(self):
        _label = '{:d}x{:d}'.format(self.width(), self.height())
        return basic_repr(self, _label)
