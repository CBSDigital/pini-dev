"""Pipeline tools for substance painter."""

import ctypes
import logging
import os
import sys

from ctypes import wintypes

import substance_painter

from pini import qt, pipe
from pini.qt import QtCore, QtWidgets, QtGui
from pini.utils import File, Dir, abs_path, single

_LOGGER = logging.getLogger(__name__)

if not hasattr(sys, 'PINI_SPAINTER_EXPORT_PRESETS'):
    sys.PINI_SPAINTER_EXPORT_PRESETS = set()


def _exec_export_textures(pub_dir, cfg, browser=False, force=False):
    """Execute texture export.

    Args:
        pub_dir (Dir): publish dir
        cfg (dict): export config
        browser (bool): open export folder in brower
        force (bool): replace existing without confirmation

    Returns:
        (dict): export result
    """

    pub_dir.mkdir()
    pub_dir.flush(force=force)
    if browser:
        assert pub_dir.exists()
        pub_dir.browser()
    _result = substance_painter.export.export_project_textures(cfg)
    if _result.status != substance_painter.export.ExportStatus.Success:
        _LOGGER.error(' - EXPORT ERROR %s', _result.message)
        raise RuntimeError('Export textures failed')

    return _result


def export_textures(
        work=None, browser=False, extn='png', size=4096, sets=None,
        progress=None, force=False):
    """Export textures from current scene.

    Args:
        work (CCPWork): work file
        browser (bool): open export folder in brower
        extn (str): texture image format
        size (int): texture size (in pixels)
        sets (str list): export only the given texture sets
        progress (ProgressDialog): progress bar
        force (bool): replace existing without confirmation

    Returns:
        (CPOutput list): texture outputs
    """
    _LOGGER.info('EXPORT TEXTURES %s', sets)

    # Find text template
    _work = work or pipe.CACHE.obt_cur_work()
    assert _work
    _tmpl_name = 'texture_seq'
    _tmpl = _work.job.find_template(_tmpl_name, dcc_='spainter', catch=True)
    if not _tmpl:
        raise RuntimeError(
            f'No "{_tmpl_name}" template found in job "{_work.job.name}" - '
            'unable to export textures')

    _pub_dir = _to_pub_dir(work=_work, template=_tmpl)
    _cfg = to_export_cfg(
        pub_dir=_pub_dir, extn=extn, size=size, sets=sets)
    _LOGGER.info(' - CFG %s', _cfg)

    # Run export
    _result = _exec_export_textures(
        pub_dir=_pub_dir, cfg=_cfg, browser=browser)
    if progress:
        progress.set_pc(50)
    _LOGGER.info(' - EXPORT COMPLETE')

    # Find exported textures to rename
    _to_rename = []
    _outs = []
    for _shd, _paths in _result.textures.items():
        _LOGGER.info(" - SHD %s", _shd)
        _shd, _ = _shd
        _LOGGER.info("   - SHD %s", _shd)
        for _path in _paths:
            _LOGGER.info('   - TEX FILE %s', _path)

            # Parse filename
            _orig_file = File(_path)
            _orig_root, _suffix = _orig_file.filename.split(f'_{_shd}_')
            _LOGGER.info('     - ROOT / SUFFIX %s %s', _orig_root, _suffix)

            # Handle udim option disabled
            if _suffix.count('.') < 2:
                # _chan_l, _extn = _suffix.rsplit('.', 2)
                raise RuntimeError(f'Failed to find UDIM in path {_path}')

            _chan_l, _udim, _extn = _suffix.rsplit('.', 2)
            _orig_seq = _orig_file.to_dir().to_seq(
                f'{_orig_root}_{_shd}_{_chan_l}.<UDIM>.{_orig_file.extn}')
            _LOGGER.info('   - ORIG SEQ %s', _orig_seq)
            assert _orig_seq[int(_udim)] == _path
            assert len(_udim) == 4
            assert _udim.isdigit()

            # Build output filename
            _chan = ''.join(_chr for _chr in _chan_l if _chr.isupper())
            _out_seq = _work.to_output(
                _tmpl, output_name=_shd, output_type=_chan, extn=_extn)
            if _out_seq in _outs:
                _LOGGER.info('     (ALREADY HANDLED)')
                continue
            _outs.append(_out_seq)
            _LOGGER.info('     -> TEX OUT %s', _out_seq)
            _to_rename.append((_orig_seq, _out_seq))

    # Rename to apply naming conventions
    _LOGGER.info('APPLY RENAME')
    for _orig_seq, _out_seq in qt.progress_bar(
            _to_rename, 'Renaming {:d} texture set{}'):
        _LOGGER.info(' - RENAME %s', _orig_seq)
        _LOGGER.info('    - TARGET %s', _out_seq)
        assert _orig_seq.exists()
        _orig_seq.move_to(_out_seq)
    _LOGGER.info(' - RENAME COMPLETE')

    return sorted(_outs)


def install_export_preset(preset):
    """Install export preset.

    Args:
        preset (str): name of preset to install
    """
    _src = File(preset)
    _subs_home = Dir(os.environ['PINI_SPAINTER_HOME'])
    _dir = _subs_home.to_subdir('assets/export-presets')
    _trg = _dir.to_file(_src.filename)
    _LOGGER.info(' - INSTALL PRESET %s', _trg)
    _src.copy_to(_trg, force=True, verbose=False)
    sys.PINI_SPAINTER_EXPORT_PRESETS.add(f'your_assets/{_trg.base}')


def take_snapshot(file_, force=False):  # pylint: disable=too-many-statements
    """Take a snapshot of the current 3D view.

    NOTE: written by claude code.

    Args:
        file_ (str): file to write to
        force (bool): overwrite file without confirmation

    Returns:
        (File): file that was written to
    """

    def _map_to_ancestor(widget, ancestor):
        """Sum widget positions up the parent chain to an ancestor.

        Avoids QWidget.mapToGlobal, which consistently errors in painter
        (passing a QPoint into api-created widgets raises a bogus
        "already deleted") - pos() takes no args so is safe.

        Args:
            widget (QWidget): widget to map
            ancestor (QWidget): ancestor to map to

        Returns:
            (int tuple): x/y offset of widget within ancestor
        """
        _x_off = _y_off = 0
        _widget = widget
        while _widget is not None and _widget is not ancestor:
            _pos = _widget.pos()
            _x_off += _pos.x()
            _y_off += _pos.y()
            _widget = _widget.parentWidget()
        return _x_off, _y_off

    def _find_3d_view(central):
        """Find the 3d view widget within the central widget.

        The central area shows 3d/2d views side by side - the 3d view
        is taken to be the leftmost tall pane which doesn't span the
        full central width.

        Args:
            central (QWidget): main window central widget

        Returns:
            (QWidget): 3d view widget (central widget if not isolated,
                eg. in 3d-only display mode where it fills the area)
        """
        _candidates = []
        for _widget in central.findChildren(QtWidgets.QWidget):
            if not _widget.isVisible():
                continue
            _width, _height = _widget.width(), _widget.height()
            if _height < 0.5 * central.height():
                continue
            if not 0.2 * central.width() < _width < 0.9 * central.width():
                continue
            _x_off, _ = _map_to_ancestor(_widget, central)
            _candidates.append((_x_off, -_width * _height, _widget))
        if not _candidates:
            _LOGGER.info(' - NO 3D PANE ISOLATED - USING FULL CENTRAL AREA')
            return central

        _candidates.sort(key=lambda _item: (_item[0], _item[1]))
        _, _, _widget = _candidates[0]
        _LOGGER.info(
            ' - 3D VIEW %s | %s | %dx%d',
            _widget.metaObject().className(), _widget.objectName(),
            _widget.width(), _widget.height())
        return _widget

    def _grab_window_image(widget):
        """Grab a top-level window's contents via win32 PrintWindow.

        Unlike grabbing the screen, this renders the window's own
        contents so overlapping windows/dialogs are not included.

        Args:
            widget (QWidget): top-level window widget

        Returns:
            (QImage): window client area image (physical pixels)
        """
        _user32 = ctypes.windll.user32
        _gdi32 = ctypes.windll.gdi32

        _hwnd = int(widget.winId())
        _rect = wintypes.RECT()
        _user32.GetClientRect(_hwnd, ctypes.byref(_rect))
        _width = _rect.right - _rect.left
        _height = _rect.bottom - _rect.top

        _hdc_win = _user32.GetDC(_hwnd)
        _hdc_mem = _gdi32.CreateCompatibleDC(_hdc_win)
        _bitmap = _gdi32.CreateCompatibleBitmap(_hdc_win, _width, _height)
        _gdi32.SelectObject(_hdc_mem, _bitmap)

        # PW_CLIENTONLY (0x1) | PW_RENDERFULLCONTENT (0x2) - the latter
        # captures gpu-composited content (ie. the 3d viewport)
        _result = _user32.PrintWindow(_hwnd, _hdc_mem, 0x1 | 0x2)
        _LOGGER.info(' - PRINTWINDOW RESULT %d (%dx%d)',
                     _result, _width, _height)

        class _BitmapInfoHeader(ctypes.Structure):
            _fields_ = [
                ('biSize', ctypes.c_uint32),
                ('biWidth', ctypes.c_int32),
                ('biHeight', ctypes.c_int32),
                ('biPlanes', ctypes.c_uint16),
                ('biBitCount', ctypes.c_uint16),
                ('biCompression', ctypes.c_uint32),
                ('biSizeImage', ctypes.c_uint32),
                ('biXPelsPerMeter', ctypes.c_int32),
                ('biYPelsPerMeter', ctypes.c_int32),
                ('biClrUsed', ctypes.c_uint32),
                ('biClrImportant', ctypes.c_uint32)]

        _info = _BitmapInfoHeader()
        _info.biSize = ctypes.sizeof(_BitmapInfoHeader)
        _info.biWidth = _width
        _info.biHeight = -_height  # negative gives top-down row order
        _info.biPlanes = 1
        _info.biBitCount = 32
        _info.biCompression = 0  # BI_RGB

        _buf = ctypes.create_string_buffer(_width * _height * 4)
        _gdi32.GetDIBits(
            _hdc_mem, _bitmap, 0, _height, _buf, ctypes.byref(_info), 0)

        _gdi32.DeleteObject(_bitmap)
        _gdi32.DeleteDC(_hdc_mem)
        _user32.ReleaseDC(_hwnd, _hdc_win)

        return QtGui.QImage(
            _buf, _width, _height, _width * 4,
            QtGui.QImage.Format_ARGB32).copy()

    def _image_is_blank(image):
        """Test whether an image is all black (ie. capture failed).

        Args:
            image (QImage): image to test

        Returns:
            (bool): whether all sample points are black
        """
        for _x_fr in (0.2, 0.5, 0.8):
            for _y_fr in (0.2, 0.5, 0.8):
                _color = image.pixelColor(
                    int(image.width() * _x_fr), int(image.height() * _y_fr))
                if _color.value():
                    return False
        return True

    def _grab_screen_image(main):
        """Grab the main window region from the screen.

        Fallback for PrintWindow failing - requires the window to be
        visible and unobstructed.

        Args:
            main (QWidget): main window widget

        Returns:
            (QImage): window image (physical pixels)
        """
        _screen = main.screen()
        _ratio = _screen.devicePixelRatio()
        _s_geo = _screen.geometry()
        _geo = main.geometry()  # top-level so already in global coords
        _pixmap = _screen.grabWindow(0)
        _rect = QtCore.QRect(
            int((_geo.x() - _s_geo.x()) * _ratio),
            int((_geo.y() - _s_geo.y()) * _ratio),
            int(_geo.width() * _ratio),
            int(_geo.height() * _ratio))
        return _pixmap.copy(_rect).toImage()

    def _snapshot_viewport(file_):
        """Save a snapshot of the 3d view.

        Captures the painter window contents directly (via win32
        PrintWindow) so windows on top are not included, then crops
        to the 3d view.

        Args:
            file_ (str): path to save image to (eg. png/jpg)

        Returns:
            (str): path to saved image
        """
        _main = substance_painter.ui.get_main_window()
        _central = _main.centralWidget()
        _view = _find_3d_view(_central)

        _image = _grab_window_image(_main)
        if _image_is_blank(_image):
            _LOGGER.warning(
                ' - PRINTWINDOW GAVE BLANK IMAGE - FALLING BACK TO '
                'SCREEN GRAB (WINDOW MUST BE UNOBSTRUCTED)')
            _image = _grab_screen_image(_main)

        # Crop to 3d view, accounting for dpi scaling
        _ratio = _main.devicePixelRatioF()
        _x_off, _y_off = _map_to_ancestor(_view, _main)
        _rect = QtCore.QRect(
            int(_x_off * _ratio), int(_y_off * _ratio),
            int(_view.width() * _ratio), int(_view.height() * _ratio))
        _image = _image.copy(_rect)

        # Crop to centred square
        _side = min(_image.width(), _image.height())
        _sq_rect = QtCore.QRect(
            (_image.width() - _side) // 2,
            (_image.height() - _side) // 2,
            _side, _side)
        _image = _image.copy(_sq_rect)

        if not _image.save(file_):
            raise RuntimeError(f'Failed to save snapshot {file_}')
        _LOGGER.info(' - SAVED SNAPSHOT %s', file_)
        return file_

    _file = File(file_)
    _file.delete(force=force)
    assert not _file.exists()
    _snapshot_viewport(_file.path)
    assert _file.exists()

    return _file


def to_export_cfg(pub_dir, extn, preset=None, size=4096, sets=None):
    """Build export config dict.

    Args:
        pub_dir (Dir): publish dir
        extn (str): export format
        preset (str): export preset url
        size (int): export size (in pixels)
        sets (str list): export only the given texture sets

    Returns:
        (dict): export config
    """

    # Determine preset
    _preset_url = preset
    if not _preset_url:
        _preset_url = os.environ.get('PINI_SPAINTER_EXPORT_PRESET')
    if not _preset_url:
        _preset_url = "starter_assets/PBR Metallic Roughness"
    _LOGGER.info(' - EXPORT PRESET %s', _preset_url)
    _ctx, _name = _preset_url.split('/')
    _preset = substance_painter.resource.ResourceID(
        context=_ctx, name=_name)

    _shds = []
    _export_list = []
    for _shd in substance_painter.textureset.all_texture_sets():
        if sets and _shd.name not in sets:
            continue
        _shds.append(_shd)
        _export_list.append({"rootPath": _shd.name})

    _cfg = {
        "exportShaderParams": False,
        "exportPath": pub_dir.path,
        "defaultExportPreset": _preset.url(),
        "exportList": _export_list,
        "exportParameters": [{
            "parameters": {
                "fileFormat": extn,
                "dithering": True,
                "paddingAlgorithm": "infinite",
                'size': size,
            }}]}

    return _cfg


def to_export_data(sets=None):
    """Build dict of export data for the current scene.

    Args:
        sets (str list): export only these sets

    Returns:
        (dict): texture set / list of export files data
    """
    _pub_dir = Dir(abs_path('~/tmp'))
    _cfg = to_export_cfg(_pub_dir, extn='png')
    _parms = single(_cfg['exportParameters'])['parameters']
    _res = _parms['size']
    _sets = [_item['rootPath'] for _item in _cfg['exportList']]

    # Build export data
    _raw_exports = substance_painter.export.list_project_textures(_cfg)
    _exports = {}
    for _set in _sets:
        if sets and _set not in sets:
            continue
        _files = _raw_exports[(_set, '')]
        _data = []
        for _file in _files:
            _data.append({
                'filename': File(_file).filename,
                'res': _res})
        _exports[_set] = _data

    return _exports


def _to_pub_dir(work, template):
    """Obtain publish dir for the given work file.

    NOTE: substance texture export handle see // mounts

    Args:
        work (CCPWork): work file
        template (CPTemplate): texture file template

    Returns:
        (Dir): publish dir
    """
    _pub_dir = work.to_output(
        template, output_name='null', output_type='C',
        udim_u='10', udim_v='01', extn='png').to_dir()
    _LOGGER.info(" - PUB DIR %s", _pub_dir)
    _pub_dir = Dir(abs_path(_pub_dir, mode='drive'))
    assert not _pub_dir.path.startswith('//')
    return _pub_dir
