"""Tools for managing ffmpeg conversions."""

import logging
import os
import time

from ..u_misc import strftime
from ..u_exe import find_exe
from ..cache import cache_result
from ..path import Dir, File, TMP_PATH, abs_path
from ..u_misc import nice_age, to_str
from ..u_system import system

_LOGGER = logging.getLogger(__name__)


@cache_result
def find_ffmpeg_exe(exe='ffmpeg'):
    """Find ffmpeg executable.

    In cases where it can't simply be added to $PATH (eg. if you don't want
    to override another ffmpeg version which is being used), the path can
    be forced us $FFMPEG_EXE.

    Args:
        exe (str): override ffmpeg exe to find (eg. ffprobe)

    Returns:
        (File): ffmpeg executable
    """
    _env_path = os.environ.get('FFMPEG_EXE')
    if _env_path:
        _exe = File(_env_path).to_file(base=exe)
        assert _exe.exists()
        return _exe
    return find_exe(exe)


def play_sound(file_, start=None, end=None, verbose=0):
    """Play the given sound.

    Args:
        file_ (File): wav file to play
        start (float): start point (in secs)
        end (float): end point (in secs)
        verbose (int): print process data
    """
    _file = File(abs_path(file_))
    _ffplay = find_exe('ffplay')
    if not _file.exists():
        raise OSError(_file.path)
    _cmds = [_ffplay, _file, '-autoexit']
    if start:
        _cmds += ['-ss', start]
    if end:
        _start = start or 0
        _dur = end - _start
        _cmds += ['-t', _dur]

    system(_cmds, result=False, verbose=verbose)


def _build_ffmpeg_audio_flags(use_scene_audio, audio, audio_offset):
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


def _build_ffmpeg_burnin_flags(seq, video, fps, height=30, inset=10):
    """Add ffmpeg burnin flags and build tmp burnin files.

    Args:
        seq (Seq): sequence being converted
        video (Video): output video
        fps (float): frame rate
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
    _seq_w, _seq_h = _res.to_tuple()
    _fade = qt.to_col(1, 1, 1, 0.5)
    _transparent = qt.to_col('Transparent')
    _LOGGER.info(' - RES %s', _res)

    # Find font
    _name = None
    _names = ["Arial", "Helvetica"]
    for _name in _names:
        _font = qt.to_font(_name)
        if _font:
            break
    else:
        _LOGGER.error(' - FAILED TO FIND FONT %s', _names)
        _font = QtGui.QFont()
    _LOGGER.info(' - FONT %s %s', _name, _font)
    _font.setPointSize(height * 0.4)

    # Draw header
    _header = Dir(TMP_PATH).to_file('pini/overlay_header.png')
    _pix = qt.CPixmap(_res[0], height)
    _pix.fill(_fade)
    _pix.draw_text(
        pipe.NAME.upper(), (inset, height / 2), anchor='L', font=_font)
    _pix.draw_text(
        strftime('%Y-%m-%d'), (_seq_w - inset - 2, height / 2),
        anchor='R', font=_font)
    if _job:
        _pix.draw_text(
            _job.name, (_seq_w / 2, height / 2), anchor='C', font=_font)
    _pix.save_as(_header, force=True, verbose=0)

    # Draw footer
    _footer = Dir(TMP_PATH).to_file('pini/overlay_footer.png')
    _pix = qt.CPixmap(_seq_w, height)
    _pix.fill(_fade)
    _pix.draw_text(
        video.base, (inset, height / 2), anchor='L', font=_font)
    _pix.save_as(_footer, force=True, verbose=0)

    # Write frame number overlays
    _path = Dir(TMP_PATH).to_file('pini/overlay_frames/frame.%04d.png')
    _frame_ns = Seq(_path)
    _frame_ns.delete(force=True)
    _frames_overlay_w = height * 6
    _LOGGER.debug(' - ADDING OVERLAY FRAMES %s', seq.to_range())
    for _frame in seq.to_frames():
        _pix = qt.CPixmap(_frames_overlay_w, height)
        _pix.fill(_transparent)
        for _num, _x_pos in [
                (_start, height),
                (_frame, height * 3),
                (_end, height * 5),
        ]:
            _pos = qt.to_p(_x_pos, height / 2)
            _pix.draw_text(
                f'{_num:04d}', pos=_pos, anchor='C', font=_font)
        for _x_pos in [height * 2, height * 4]:
            _pos = qt.to_p(_x_pos, height / 2)
            _pix.draw_text('-', pos=_pos, anchor='C', font=_font)
        _pix.save_as(_frame_ns[_frame], force=True, verbose=0)

    # Build flags
    _over_w = _seq_w - _frames_overlay_w - inset + 10
    _over_h = _seq_h - height + 1
    _filters = [
        'overlay=0:0[header]',
        f'[header]overlay=0:{_res[1]-height:d}[footer]',
        f'[footer]overlay={_over_w:d}:{_over_h:d}',
    ]
    _filter_complex = ';'.join(_filters)
    _flags = [
        '-i', _header,
        '-i', _footer,
        '-framerate', fps,
        '-f', 'image2',
        '-start_number', _start, '-i', _frame_ns.path,
        '-filter_complex', _filter_complex,
    ]

    return _flags


def read_ffprobe(video):
    """Read ffprobe result for the given video file.

    Args:
        video (Video): video file to read

    Returns:
        (str): ffprobe result
    """
    _ffprobe_exe = find_ffmpeg_exe(exe='ffprobe')

    _cmds = [_ffprobe_exe.path, video.path]
    _LOGGER.debug(' - CMD %s', ' '.join(_cmds))
    _result = system(_cmds, result='err', decode='latin-1')
    _lines = [_line.strip() for _line in _result.split('\n')]

    return _lines


def seq_to_video(
        seq, video, fps=None, audio=None, audio_offset=0.0,
        use_scene_audio=False, crf=15, bitrate=None, denoise=None,
        tune=None, speed=None, burnins=False, res=None, range_=None,
        verbose=0):
    """Build video file using ffmpeg.

    Args:
        seq (Seq): source sequence
        video (File): file to create
        fps (float): frame rate
        audio (File): apply audio
        audio_offset (float): audio offset in secs
        use_scene_audio (bool): apply audio from current scene
            (overrides all other audio flags)
        crf (int): constant rate factor (default is 25,
            visually lossless is 15, highest is 1)
        bitrate (str): apply bitrate to conversion (eg. 1M)
        denoise (float): apply nlmeans denoise (20.0 is recommended)
        tune (str): apply tuning preset (eg. animation, film)
        speed (str): apply speed preset (eg. slow, medium, slowest)
        burnins (bool): add burnins
        res (tuple): override resolution
        range_ (tuple): override frame range
        verbose (int): print process data

    Returns:
        (Video): video file
    """
    from pini import dcc

    _video = File(abs_path(to_str(video)))
    _ffmpeg = find_ffmpeg_exe()
    _fps = fps or dcc.get_fps()
    if range_:
        _start, _end = range_
        _n_frames = _end - _start + 1
    else:
        _start, _ = seq.to_range(force=True)
        _n_frames = None
    assert _ffmpeg
    assert _fps

    # Build args list
    _args = [_ffmpeg]
    _args += ['-framerate', _fps, '-f', 'image2']
    if _start != 1:
        _args += ['-start_number', _start]
    _args += ['-i', seq.path]
    if _n_frames:
        _args += ['-frames:v', _n_frames]
    # if colspace:
    #     if colspace == 'sRGB':
    #         _args += ['-color_trc', 'iec61966_2_1']
    #     else:
    #         raise NotImplementedError(colspace)
    if burnins:
        _args += _build_ffmpeg_burnin_flags(seq, video=_video, fps=_fps)
    _args += _build_ffmpeg_audio_flags(
        use_scene_audio=use_scene_audio, audio=audio,
        audio_offset=audio_offset)
    _args += ['-framerate', _fps]
    _args += ['-vcodec', 'libx264']
    _args += ['-pix_fmt', 'yuv420p']
    if bitrate:
        _args += ['-b:v', bitrate]
    else:
        _args += ['-crf', crf]
    if speed:
        _args += ['-preset', speed]
    if tune:
        _args += ['-tune', tune]
    if denoise:
        _args += ['-vf', f"nlmeans='{denoise:.01f}:7:5:3:3'"]
    if res:
        _args += ['-vf', f'scale={res[0]:d}:{res[1]:d}']
    _args += [_video]

    # Execute ffmpeg
    _LOGGER.debug(' - FFMPEG %s', _args)
    _LOGGER.debug(
        ' - FFMPEG %s',
        ' '.join(to_str(_arg) for _arg in _args))
    _, _err = system(_args, result='out/err', verbose=verbose)
    if not _video.exists() or not _video.size():
        _handle_conversion_fail(seq=seq, err=_err, video=_video, args=_args)

    return _video


def _handle_conversion_fail(seq, video, err, args):
    """Handle conversion fail, flaggin common issues.

    Args:
        seq (Seq): source image sequence
        video (Video): conversion target
        err (str): ffmpeg error message
        args (str): ffmpeg command args
    """
    _LOGGER.info('CONVERSION FAILED:\n%s', err)
    _args_s = ''
    for _arg in args:
        _arg = to_str(_arg)
        if ' ' in _arg:
            _arg = f'"{_arg}"'
        _args_s += f'{_arg} '
    _LOGGER.info(' - ARGS %s', _args_s)

    if not video.size():
        video.delete(force=True)

    # Compression fail
    if 'Compression 8 is not implemented' in err:
        raise RuntimeError('Unsupported compression ' + seq.path)

    # Res fail
    if (
            'height not divisible by 2' in err or
            'width not divisible by 2' in err):
        _res = seq.to_res()
        raise RuntimeError(
            f'Unsupported resolution {_res[0]:d}x{_res[1]:d} (H264 requires '
            f'width and height be divisible by two) - {seq.path}')

    raise RuntimeError('Conversion failed ' + seq.path)


def video_to_frame(video, file_, res=None, frame=None, force=False):
    """Extract a frame from a video.

    Args:
        video (Video): source video
        file_ (File): output file path
        res (tuple): apply width/height
        frame (int): select frame to export (default is middle frame)
        force (bool): overwrite existing without confirmation

    Returns:
        (File): output image
    """
    _LOGGER.info('TO FRAMES %s', video.path)
    _img = File(file_)
    _img.delete(force=force)
    _img.test_dir()

    if frame is not None:
        _time = frame / video.to_fps()
    else:
        _time = video.to_dur() / 2
    _LOGGER.info(' - TIME %f', _time)

    # Build ffmpeg commands
    _ffmpeg = find_ffmpeg_exe()
    _cmds = [
        _ffmpeg,
        '-ss', _time,
        '-i', video,
        '-frames:v', 1]
    if res:
        _cmds += ['-vf', f'scale={res[0]:d}:{res[1]:d}']
    _cmds += [_img]

    assert not _img.exists()
    _out, _err = system(_cmds, result='out/err', verbose=1)
    if not _img.exists():
        _LOGGER.info('OUT %s', _out)
        _LOGGER.info('ERR %s', _err)
        raise RuntimeError('Failed to export image ' + _img.path)

    return _img


def video_to_seq(video, seq, fps=None, res=None, force=False, verbose=1):
    """Convert a video to an image sequence.

    Args:
        video (Video): source video
        seq (Seq): output image sequence
        fps (float): override frame rate
        res (tuple): override resolution
        force (bool): overwrite existing without confirmation
        verbose (int): print process data

    Returns:
        (Seq): output sequence
    """
    from .. import clip

    _LOGGER.info('VIDEO TO SEQ %s', video.path)
    _LOGGER.info(' - TARGET %s', seq.path)

    _fps = fps or video.to_fps()
    _LOGGER.info(' - FPS %s', _fps)

    # Check output seq
    assert isinstance(seq, clip.Seq)
    seq.delete(force=force)
    seq.test_dir()

    # Build ffmpeg commands
    _ffmpeg = find_ffmpeg_exe()
    _cmds = [
        _ffmpeg,
        '-i', video,
        '-r', _fps]
    if res:
        _cmds += ['-vf', f'scale={res[0]:d}:{res[1]:d}']
    _cmds += [seq]

    # Execute ffmpeg
    _start = time.time()
    _out, _err = system(_cmds, result='out/err', verbose=verbose)
    seq.to_frames(force=True)
    if not seq.exists():
        _LOGGER.info('OUT %s', _out)
        _LOGGER.info('ERR %s', _err)
        raise RuntimeError('Failed to compile seq ' + seq.path)

    _f_start, _f_end = seq.to_range()
    _LOGGER.info(' - WROTE FRAMES %d-%d IN %s', _f_start, _f_end,
                 nice_age(time.time() - _start))

    return seq
