"""Tool for managing playblasting."""

import logging
import os
import time

from maya import cmds
from maya.app.general import createImageFormats

from pini.utils import Seq, str_to_ints, File, TMP, single, safe_zip, Video

from .mu_dec import reset_ns
from .mu_namespace import del_namespace, set_namespace

_LOGGER = logging.getLogger(__name__)
_BLAST_TMP_NS = os.environ.get('PINI_BLAST_TMP_NAMESPACE', 'BlastTmp')


@reset_ns
def _build_tmp_blast_cam(cam):
    """Build tmp camera.

    This allows camera settings to be changed without affecting the
    scene camera.

    NOTE: originally this was having its transforms reset, but resetting the
    scale was affecting the clipping planes, so this was removed.

    Args:
        cam (str): camera to duplicate

    Returns:
        (CCamera): tmp camera
    """
    _LOGGER.debug(' - BUILD TMP BLAST CAM %s', cam)
    from maya_pini import open_maya as pom

    set_namespace(f':{_BLAST_TMP_NS}', clean=True)

    # Duplicate camera
    _src = pom.CCamera(cam)
    _cam = _src.duplicate(upstream_nodes=True)
    _LOGGER.debug('   - TMP CAM %s', _cam)

    # Remove unwanted nodes in tmp ns
    _nodes = cmds.ls(f'{_BLAST_TMP_NS}:*')
    for _node in _nodes:
        if _node in [_cam, _cam.shp]:
            continue
        if not cmds.objExists(_node):
            continue
        _type = cmds.objectType(_node)
        if _type in ('imagePlane', 'expression'):
            continue
        if _type == 'transform' and '->' in _node:
            continue
        _LOGGER.debug('     - REMOVE %s (%s)', _node, _type)
        cmds.delete(_node)

    # Unlock attrs
    for _plug in [_cam.plug[_attr] for _attr in 'trs'] + _cam.tfm_plugs:
        _LOGGER.debug('   - UNLOCK %s', _plug)
        _plug.set_locked(False)

    _src.parent_constraint(_cam, force=True)

    # Fix any image place colspaces - it seems these are not necessarily
    # made to match on duplicate
    for _src_plane, _cam_plane in safe_zip(
            _src.shp.find_incoming(
                type_='imagePlane', plugs=False, connections=False),
            _cam.shp.find_incoming(
                type_='imagePlane', plugs=False, connections=False),
    ):
        _LOGGER.debug(
            ' - CHECK IMG PLANE COLSPACE %s %s', _src_plane, _cam_plane)
        _space = _src_plane.shp.plug['colorSpace'].get_val()
        _LOGGER.debug('   - APPLY COLSPACE %s', _space)
        _cam_plane.shp.plug['colorSpace'].set_val(_space)

    return _cam


def _build_tmp_viewport_window(res, camera, show=False, settings='Nice'):
    """Build tmp blast viewport window to blast through.

    This allows the blast windows size to be changed to match the blast
    res (otherwise maya either blasts using the viewport res or crops it
    weirdly, changing the framing) and also allows a temporary model
    editor to be used, so settings don't need to be reverted after blast.

    Args:
        res (tuple): blast width/height
        camera (str): blast camera
        show (bool): show the window (not necessary for blast)
        settings (str): blast settings mode

    Returns:
        (tuple): window/editor
    """
    from maya_pini import ui

    _LOGGER.debug(' - BUILD TMP VIEWPORT BlastEditor')
    _width, _height = res

    # Clean existing
    if cmds.window('BlastWindow', exists=True):
        cmds.deleteUI('BlastWindow')
    if cmds.window('BlastEditor', exists=True):
        cmds.modelEditor('BlastEditor')

    # Read settings from active viewport to mimic
    _editor_tmpl = ui.get_active_model_editor()
    _editor_attrs = {}
    for _attr in ui.to_model_editor_attrs():
        _editor_attrs[_attr] = cmds.modelEditor(
            _editor_tmpl, query=True, **{_attr: True})
    _LOGGER.debug(' - COPIED EDITOR SETTINGS  %s', _editor_attrs)

    # Build the window
    _window = cmds.window('BlastWindow', title='Blast Window')
    _form = cmds.formLayout()
    _editor = cmds.modelEditor('BlastEditor', camera=camera, **_editor_attrs)
    _LOGGER.debug(' - CREATED NEW EDITOR %s', _editor)
    cmds.formLayout(
        _form, edit=True,
        attachForm=[
            (_editor, 'top', 0),
            (_editor, 'left', 0),
            (_editor, 'top', 0),
            (_editor, 'bottom', 0),
            (_editor, 'right', 0)])

    # Apply viewport settings
    _me_settings = {}
    if settings == 'Nice':
        _me_settings = {
            'cameras': False,
            'grid': False,
            'headsUpDisplay': False,
            'joints': False,
            'locators': False,
            'nurbsCurves': False,
            'selectionHiliteDisplay': False,
        }
    elif settings == 'As is':
        pass
    else:
        raise ValueError(settings)
    _LOGGER.debug(' - OVERRIDDEN EDITOR SETTINGS  %s', _me_settings)
    if _me_settings:
        cmds.modelEditor(_editor, edit=True, **_me_settings)

    # Apply camera settings
    cmds.camera(camera, edit=True, **{
        'overscan': 1,
        'displayResolution': False,
        'panZoomEnabled': False})
    _LOGGER.debug(' - APPLY CAM %s %s %s', _editor, camera, type(camera))
    cmds.modelEditor(_editor, edit=True, camera=camera)
    if show:
        cmds.showWindow(_window)
    cmds.window(_window, edit=True, width=_width, height=_height)

    return _window, _editor


def _exec_blast(
        seq, range_=None, res=None, camera=None, cleanup=True, settings='Nice',
        use_tmp_cam=True, use_tmp_viewport=True):
    """Execute the blast.

    Args:
        seq (Seq): blast image sequence
        range_ (tuple): blast range
        res (tuple): blast res
        camera (str): blast camera
        cleanup (bool): cleanup tmp window/cam
        settings (str): blast settings mode
        use_tmp_cam (bool): use tmp camera
        use_tmp_viewport (bool): use tmp viewport
    """
    from maya_pini import ui

    _LOGGER.debug('BLAST')
    assert isinstance(seq, Seq)

    _start, _end = range_

    # Setup cam
    _tmp_cam = None
    _blast_cam = camera
    if use_tmp_cam:
        _tmp_cam = _build_tmp_blast_cam(camera)
        _blast_cam = _tmp_cam
    _LOGGER.debug(' - BLAST CAM %s %s', camera, _blast_cam)

    # Setup window
    _tmp_window = None
    if use_tmp_viewport:
        _tmp_window, _blast_editor = _build_tmp_viewport_window(
            res=res, camera=_blast_cam, show=not cleanup, settings=settings)
    else:
        _blast_editor = ui.get_active_model_editor()

    # Set image format
    _fmt_mgr = createImageFormats.ImageFormats()
    _fmt_mgr.pushRenderGlobalsForDesc({
        'jpg': "JPEG",
    }.get(seq.extn, seq.extn.upper()))

    _filename = f'{seq.dir}/{seq.base}'
    _LOGGER.debug(' - BLAST FILENAME %s', _filename)
    _LOGGER.debug(' - START/END %d/%d', _start, _end)
    cmds.playblast(
        startTime=_start, endTime=_end, format='image', filename=_filename,
        viewer=False, widthHeight=res, offScreen=True, forceOverwrite=True,
        percent=100, editorPanelName=_blast_editor)
    _LOGGER.debug(' - PLAYBLAST CMD COMPLETE')
    assert seq.to_frames(force=True)
    if cleanup:
        if _tmp_window:
            _LOGGER.debug(' - DELETE TMP WINDOW %s', _tmp_window)
            cmds.deleteUI(_tmp_window)
        if _tmp_cam:
            _LOGGER.debug(' - DELETE TMP CAM %s', _tmp_cam)
            cmds.delete(_tmp_cam)
        _LOGGER.debug(' - DELETE TMP NS %s', _BLAST_TMP_NS)
        del_namespace(':' + _BLAST_TMP_NS, force=True)
    _LOGGER.debug(' - CLEANUP COMPLETE')

    _LOGGER.debug(' - POPPED GLOBALS')
    _fmt_mgr.popRenderGlobals()
    _LOGGER.debug(' - BLAST COMPLETE')


def _make_video_res_even(res):
    """Make sure video width/height are even to avoid ffmpeg/h264 error.

    If either dimension is odd, an extra pixel is added.

    eg. 123x156 -> 124x156

    Args:
        res (list): resolution to update

    Returns:
        (list): updated resolution
    """
    _res = list(res)
    _fixed = False
    for _idx, _dim in enumerate(res):
        if _dim % 2:
            _fixed = True
            _res[_idx] += 1
    if _fixed:
        _LOGGER.warning(' - UPDATED RES FOR H264 %s', _res)

    return _res


def _to_range(range_):
    """Determine blast range.

    Args:
        range_ (str|tuple): override blast range

    Returns:
        (tuple): blast start/end
    """
    from pini import dcc

    if not range_:
        return dcc.t_range(int)

    if isinstance(range_, (tuple, list)):
        if len(range_) == 2:  # start/end frames
            return tuple(range_)
        if len(range_) == 1:  # single frame
            _frame = single(range_)
            return _frame, _frame
        raise ValueError(range_)

    # Interpret as string (eg. 1001-1100)
    if isinstance(range_, str):
        _frames = str_to_ints(range_)
        return _frames[0], _frames[-1]

    raise ValueError(range_)


def _to_res(res, is_video):
    """Determine blast resolution.

    Args:
        res (str|tuple): overide blast res - eg. Full, Half, (1024, 768)
        is_video (bool): whether this blast to be converted to video

    Returns:
        (tuple): blast width/height
    """
    from pini import dcc

    if res in (None, 'Full'):
        _res = dcc.get_res()
    elif res == 'Half':
        _revert_res = dcc.get_res()
        _res = [int(_item / 2) for _item in dcc.get_res()]
    elif res == 'Quarter':
        _revert_res = dcc.get_res()
        _res = [int(_item / 4) for _item in dcc.get_res()]
    elif res == '1920 Width':
        _width, _height = dcc.get_res()
        _aspect = _width / _height
        _res = [1920, round(1920 / _aspect)]
    else:
        raise ValueError(res)

    # Fix non-even video res
    if is_video:
        _res = _make_video_res_even(_res)

    return _res


def blast(
        clip, camera=None, range_=None, settings='As is', res='Full',
        use_scene_audio=True, view=False, cleanup=True, burnins=False,
        tmp_seq=None, frame_to_thumb=None, force=False):
    """Execute playblast.

    Args:
        clip (Clip): output Seq/Video
        camera (str): force camera to blast through
        range_ (tuple): override blast range
        settings (str): blast settings mode
        res (str|tuple): overide blast res - eg. Full, Half, (1024, 768)
        use_scene_audio (bool): apply scene audio to blast videos
        view (bool): view blast on completion
        cleanup (bool): clean up tmp nodes/files
        burnins (bool): write burnins (on video compile only)
        tmp_seq (Seq): override tmp sequence path for mp4 blast
        frame_to_thumb (File): copy a frame of the blast to this path
        force (bool): overwrite existing without confirmation
    """
    from pini import qt
    from pini.tools import error
    from maya_pini import open_maya as pom

    _clip = clip
    if isinstance(_clip, str):
        _class = Seq if '%04d' in _clip else Video
        _clip = _class(clip)

    _cam = camera or pom.active_cam()
    _is_video = _clip.extn in ('mp4', 'mov')
    _range = _to_range(range_)
    _res = _to_res(res, is_video=_is_video)

    _LOGGER.debug('BLAST')
    _LOGGER.debug(' - CAM %s', _cam)
    _LOGGER.debug(' - RANGE %s', _range)
    _LOGGER.debug(' - RES %s', _res)

    # Prepare output paths
    if _is_video:
        _tmp_seq = tmp_seq or TMP.to_seq('pini/MayaBlast/blast.%04d.jpg')
        _tmp_seq.delete(force=True)
    else:
        _tmp_seq = None
    try:
        _clip.delete(force=force, wording='replace')
    except OSError as _exc:
        raise error.HandledError(
            f'Unable to delete existing file:\n\n{_clip.path}\n\n'
            f'This could be caused by having the file open already in a '
            f'viewing application (eg. rv).') from _exc
    _clip.test_dir()
    _seq = _tmp_seq or _clip
    _LOGGER.debug(' - SEQ %s', _seq)
    assert isinstance(_seq, Seq)
    assert not _seq.exists()

    # Execute blast
    _start = time.time()
    pom.set_render_cam(_cam)
    _exec_blast(
        seq=_seq, range_=_range, camera=_cam, res=_res, cleanup=cleanup,
        settings=settings)
    if frame_to_thumb:
        _copy_frame_as_thumb(
            image=_seq.to_frame_file(), thumb=frame_to_thumb)

    if _tmp_seq:
        _tmp_seq.to_video(
            _clip, use_scene_audio=use_scene_audio, burnins=burnins, verbose=1)
        if cleanup:
            if _tmp_seq.to_range() != _range:
                _LOGGER.debug(' - TMP %s %s', _tmp_seq.to_range(), _tmp_seq)
                raise qt.DialogCancelled(
                    'Range mismatch - blast probably cancelled')
            _tmp_seq.delete(force=True)
    if not _clip.exists():
        raise RuntimeError(_clip.path)
    if view:
        _clip.view()
    _LOGGER.debug(' - BLAST COMPLETE IN %.02fs', time.time() - _start)


def _copy_frame_as_thumb(image, thumb, max_aspect=2.0, height=100):
    """Copy frame as thumbnail.

    Copies the file to the given path, limiting the height and aspect
    ratio to normalise thumb sizes.

    Args:
        image (str): path to source timage
        thumb (str): path to save image to
        max_aspect (float): aspect limit for thumb
        height (int): thumb height
    """
    from pini import qt
    _LOGGER.debug('COPY FRAME AS THUMB')
    _pix = qt.CPixmap(image)
    _LOGGER.debug(' - RES %s', _pix.size())
    _pix = _pix.resize(height=height)
    _LOGGER.debug(' - RES %s', _pix.size())
    _LOGGER.debug(' - ASPECT %s', _pix.aspect())
    if _pix.aspect() > max_aspect:
        _crop = int((_pix.width() - (_pix.height() * max_aspect)) / 2)
        _LOGGER.debug(' - CROP %d', _crop)
        _pix = _pix.crop(left=_crop, right=_crop)
    _LOGGER.debug(' - RES %s', _pix.size())
    _pix.save_as(thumb, force=True)


def blast_frame(file_, settings='Nice', force=False):
    """Blast a single frame.

    Args:
        file_ (File): file to write to
        settings (str): blast settings mode
        force (bool): overwrite without confirmation
    """
    _file = File(file_)
    _file.delete(force=force, wording='replace')
    _frame = int(cmds.currentTime(query=True))
    _rng = [_frame]
    _tmp_seq = TMP.to_seq('tmp.%04d.' + file_.extn)
    _tmp_seq.delete(force=True)
    assert not _tmp_seq.exists()
    blast(clip=_tmp_seq, range_=_rng, settings=settings)
    assert _tmp_seq.exists()
    _tmp_file = File(_tmp_seq[_frame])
    _tmp_file.move_to(_file)
