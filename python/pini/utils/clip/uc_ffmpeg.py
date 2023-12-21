"""Tools for managing ffmpeg conversions."""

import logging

from ..u_misc import strftime
from ..path import Dir, File, TMP_PATH

_LOGGER = logging.getLogger(__name__)


def build_ffmpeg_audio_flags(use_scene_audio, audio, audio_offset):
    """Add audio flags for ffmpeg.

    Args:
        use_scene_audio (bool): read audio from current scene
        audio (str): path to audio file
        audio_offset (float): audio offset in seconds

    Returns:
        (str list): audio flags
    """
    from pini import dcc

    # Determine audio + offset
    if use_scene_audio:
        _audio, _audio_offs = dcc.get_audio()
        _LOGGER.info('AUDIO %s %s', _audio, _audio_offs)
    else:
        _audio = audio
        _audio_offs = audio_offset

    # Build flags
    _args = []
    if _audio:
        _audio = File(_audio)
        assert _audio.exists()
        if _audio_offs:
            _args += ['-itsoffset', str(_audio_offs)]
        _args += ['-i', _audio, '-shortest']

    return _args


def build_ffmpeg_burnin_flags(seq, video, height=30, inset=10):
    """Add ffmpeg burnin flags and build tmp burnin files.

    Args:
        seq (Seq): sequence being converted
        video (Video): output video
        height (int): burnin height on top/bottom
        inset (int): burnin inset from sides

    Returns:
        (str list): burnin flags
    """
    from pini import qt, pipe
    from pini.qt import QtGui
    from pini.utils import Seq

    _job = pipe.to_job(video.path, catch=True)
    _start, _end = seq.to_range(force=True)
    _res = seq.to_res()
    _seq_w, _seq_h = _res
    _fade = qt.to_col(1, 1, 1, 0.5)
    _transparent = qt.to_col('Transparent')
    _LOGGER.info(' - RES %s', _res)

    # Find font
    _names = ["Arial", "Helvetica"]
    for _name in _names:
        _font = qt.to_font(_name)
        if _font:
            break
    else:
        _LOGGER.error(' - FAILED TO FIND FONT %s', _names)
        _font = QtGui.QFont()
    _LOGGER.info(' - FONT %s %s', _name, _font)
    _font.setPointSize(height*0.4)
    _metrics = QtGui.QFontMetrics(_font)

    # Draw header
    _header = Dir(TMP_PATH).to_file('pini/overlay_header.png')
    _pix = qt.CPixmap(_res[0], height)
    _pix.fill(_fade)
    _pix.draw_text(
        pipe.NAME.upper(), (inset, height/2), anchor='L', font=_font)
    _pix.draw_text(
        strftime('%Y-%m-%d'), (_seq_w-inset-2, height/2),
        anchor='R', font=_font)
    if _job:
        _pix.draw_text(_job.name, (_seq_w/2, height/2), anchor='C', font=_font)
    _pix.save_as(_header, force=True, verbose=0)

    # Draw footer
    _footer = Dir(TMP_PATH).to_file('pini/overlay_footer.png')
    _pix = qt.CPixmap(_seq_w, height)
    _pix.fill(_fade)
    _pix.draw_text(
        video.base, (inset, height/2), anchor='L', font=_font)
    _pix.save_as(_footer, force=True, verbose=0)

    # Write frame number overlays
    _path = Dir(TMP_PATH).to_file('pini/overlay_frames/frame.%04d.png')
    _frame_ns = Seq(_path)
    _frame_ns.delete(force=True)
    _frames_overlay_w = height*6
    for _frame in seq.to_frames():
        _pix = qt.CPixmap(_frames_overlay_w, height)
        _pix.fill(_transparent)
        for _num, _x_pos in [
                (_start, height),
                (_frame, height*3),
                (_end, height*5),
        ]:
            _pos = qt.to_p(_x_pos, height/2)
            _pix.draw_text(
                '{:04d}'.format(_num), pos=_pos, anchor='C', font=_font)
        for _x_pos in [height*2, height*4]:
            _pos = qt.to_p(_x_pos, height/2)
            _pix.draw_text('-', pos=_pos, anchor='C', font=_font)
        _pix.save_as(_frame_ns[_frame], force=True, verbose=0)

    # Build flags
    _filters = [
        'overlay=0:0[header]',
        '[header]overlay=0:{:d}[footer]'.format(_res[1]-height),
        '[footer]overlay={:d}:{:d}'.format(
            _seq_w - _frames_overlay_w - inset + 10,
            _seq_h - height + 1),
    ]
    _filter_complex = ';'.join(_filters)
    _flags = [
        '-i', _header,
        '-i', _footer,
        '-f', 'image2',
        '-start_number', _start,
        '-i', _frame_ns.path,
        '-filter_complex', _filter_complex,
    ]

    return _flags
