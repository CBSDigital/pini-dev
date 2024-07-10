"""Utilities for rendering."""

import logging
import time

from maya import cmds, mel

from pini import icons
from pini.utils import File, single, find_exe, system, check_heart

_LOGGER = logging.getLogger(__name__)


def _apply_globals_settings(path, col_mgt=None, animation=False):
    """Apply settings to render global nodes.

    Args:
        path (File|Seq): path being rendered
        col_mgt (bool): apply colour management
        animation (bool): apply animation settings
    """

    # Determine col management
    _col_mgt = col_mgt
    if _col_mgt is None:
        _col_mgt = {'jpg': True}.get(path.extn, False)

    cmds.setAttr("defaultArnoldRenderOptions.abortOnError", False)
    cmds.setAttr("defaultArnoldRenderOptions.abortOnLicenseFail",
                 True)  # Avoid watermark
    cmds.setAttr("defaultArnoldDriver.mergeAOVs", True)
    _extn = {'jpg': 'jpeg'}.get(path.extn, path.extn)
    cmds.setAttr('defaultArnoldDriver.aiTranslator', _extn, type='string')
    cmds.setAttr("defaultArnoldDriver.colorManagement", int(_col_mgt))
    cmds.setAttr('defaultArnoldDriver.prefix',
                 "{}/{}".format(path.dir, path.base), type='string')
    _LOGGER.debug(' - COL MGT %d', _col_mgt)

    cmds.setAttr("defaultRenderGlobals.animation", animation)
    if animation:
        cmds.setAttr('defaultRenderGlobals.outFormatControl', 0)
        cmds.setAttr('defaultRenderGlobals.putFrameBeforeExt', True)
        cmds.setAttr('defaultRenderGlobals.extensionPadding', 4)

    _LOGGER.debug(' - SETUP ARNOLD')


def render_frame(
        file_, camera=None, layer='defaultRenderLayer', col_mgt=None,
        res=None, mode='mel', pre_frame=None, pre_frame_mel=None,
        post_frame=None, post_frame_mel=None, force=False):
    """Render a frame to disk.

    Args:
        file_ (str): path to file to render to
        camera (str): force render camera
        layer (str): force render layer
        col_mgt (bool): apply colour management
        res (tuple): override render resolution
        mode (str): how to execute render (mel/api)
        pre_frame (fn): pre frame function to execute
        pre_frame_mel (str): pre frame mel to execute
        post_frame (str): post frame function to execute
        post_frame_mel (str): post frame mel to execute
        force (bool): overwrite without confirmation
    """
    from maya_pini import open_maya as pom

    _ren = cmds.getAttr("defaultRenderGlobals.currentRenderer")
    if _ren != 'arnold':
        raise NotImplementedError(_ren)

    _LOGGER.debug('RENDER FRAME force=%d', force)
    cmds.loadPlugin('mtoa', quiet=True)
    _LOGGER.debug(' - LOADED PLUGIN')

    # Check renderer
    _renderer = cmds.getAttr(
        "defaultRenderGlobals.currentRenderer", asString=True)
    if _renderer != 'arnold':
        cmds.setAttr(
            "defaultRenderGlobals.currentRenderer", 'arnold', type='string')
        _renderer = cmds.getAttr(
            "defaultRenderGlobals.currentRenderer", asString=True)
    assert _renderer == 'arnold'
    _quality = cmds.getAttr('defaultArnoldDriver.quality')
    _LOGGER.debug(' - CHECK QUALITY %d', _quality)
    assert _quality == 100

    # Get camera
    _cam = camera
    if not _cam:
        _cam = pom.find_render_cam()
    _LOGGER.debug(' - CAM %s', _cam)

    # Prepare output path
    _file = File(file_)
    _file.test_dir()
    _file.delete(force=force, wording='Replace')

    # Get res
    if not res:
        _res_x = cmds.getAttr('defaultResolution.width')
        _res_y = cmds.getAttr('defaultResolution.height')
    else:
        _res_x, _res_y = res
    _LOGGER.debug(' - RES %dx%d', _res_x, _res_y)

    _apply_globals_settings(_file, col_mgt=col_mgt)

    # Execute render
    check_heart()
    check_heart('~/.render_heart')
    if pre_frame:
        pre_frame()
    if pre_frame_mel:
        _LOGGER.info(' - EXECUTING PRE FRAME MEL %s', pre_frame_mel)
        mel.eval(pre_frame_mel)
    _exec_frame_render(
        file_=_file, mode=mode, layer=layer, res=[_res_x, _res_y], cam=_cam)
    if post_frame:
        post_frame()
    if post_frame_mel:
        _LOGGER.info(' - EXECUTING POST FRAME MEL %s', post_frame_mel)
        mel.eval(post_frame_mel)

    # Reset prefix (can interfere with other render engines eg. deadline)
    cmds.setAttr('defaultArnoldDriver.prefix', '', type='string')
    _LOGGER.debug(' - RENDER COMPLETE')


def _exec_frame_render(file_, mode, layer, res, cam):
    """Execute frame render.

    Args:
        file_ (File): path to image
        mode (str): render mode
        layer (str): force render layer
        res (tuple): render resolution
        cam (CCamera): render camera
    """
    from maya_pini import open_maya as pom

    _LOGGER.debug(' - FILE %s', file_)
    assert not file_.exists()
    assert '~' not in file_.path
    _LOGGER.debug(' - DOES NOT EXIST')

    if mode == 'api':  # Deprecated ~2020
        from mtoa.cmds import arnoldRender
        arnoldRender.arnoldRender(
            res[0], res[1], True, True, cam, ' -layer '+layer)
    elif mode == 'mel':
        if layer != pom.cur_render_layer():
            raise NotImplementedError(layer)
        cmds.renderWindowEditor('renderView', edit=True, currentCamera=cam)
        mel.eval('renderSequence')
    else:
        raise ValueError(mode)
    _LOGGER.debug(' - EXECUTED RENDER')

    # Catch arnold appended _1 to filename
    if not file_.exists():
        _LOGGER.debug(' - FILE MISSING %s', file_)
        _tmp_file = file_.to_file(base=file_.base+'_1')
        assert _tmp_file.exists()
        _LOGGER.debug(' - TMP FILE %s', _tmp_file)
        _tmp_file.move_to(file_)

    assert file_.exists()


def _exec_cmdline_render(
        seq, camera, frames, pre_frame_mel, post_frame_mel, verbose):
    """Execute a command line render using the Render command.

    Args:
        seq (Seq): image sequence to render to
        camera (str): render camera
        frames (int list): frames to render
        pre_frame_mel (str): pre frame mel to execute
        post_frame_mel (str): post frame mel to execute
        verbose (int): print process data
    """
    from pini import dcc
    from maya_pini import open_maya as pom

    _file = dcc.cur_file()
    _cam = str(camera or pom.active_cam())
    _apply_globals_settings(seq, animation=True)

    # Build cmds
    _cmds = [
        find_exe('Render').path,
        '-im', seq.base,
        '-rd', seq.dir,
        '-s', str(frames[0]),
        '-e', str(frames[-1]),
        '-cam', _cam,
        '-rl', pom.cur_render_layer().pass_name]
    if pre_frame_mel:
        _cmds += ['-preFrame', pre_frame_mel]
    if post_frame_mel:
        _cmds += ['-postFrame', post_frame_mel]

    dcc.save()
    _cmds += [_file]
    _start = time.time()
    _LOGGER.info(' - CMDS %s', ' '.join(_cmds))
    cmds.refresh()
    _out, _err = system(_cmds, result='out/err', verbose=1)

    # Handle output
    _out = _out.replace('\r', '')
    _err = _err.replace('\r', '')

    # Handle render fail
    if not seq.exists(frames=frames, force=True):
        if verbose:
            _LOGGER.info(' - OUT %s', _out)
            _LOGGER.info(' - ERR %s', _err)
        if (
                'aborting render because the abort_on_license_fail option '
                'was enabled' in _out):
            raise RuntimeError('Licence fail')
        raise RuntimeError('Cmdline render failed')

    if verbose > 1:
        _LOGGER.info(' - OUT %s', _out)
        _LOGGER.info(' - ERR %s', _err)
    _LOGGER.info(' - COMPLETED IN %.01fs', time.time() - _start)


def render(
        seq, camera=None, frames=None, view=False, mode=None,
        pre_frame=None, pre_frame_mel=None,
        post_frame=None, post_frame_mel=None,
        verbose=1):
    """Render the current scene.

    Args:
        seq (Seq): image sequence to render to
        camera (str): force render camera
        frames (int list): override list of frames to render
        view (bool): view render on completion
        mode (str): render mode
            None - use default render mode
            mel - render using renderSequence mel (does not work in batch mode)
            api - use arnold api render (deprecated)
            cmdline - force shell out to cmdline render
        pre_frame (fn): pre frame function to execute
        pre_frame_mel (str): pre frame mel to execute
        post_frame (fn): post frame function to execute
        post_frame_mel (str): post frame mel to execute
        verbose (int): print process data
    """
    from pini import dcc, qt
    _LOGGER.info('RENDER %s', seq)

    _frames = dcc.t_frames() if frames is None else frames
    _LOGGER.info(' - FRAMES %d - %d', min(_frames), max(_frames))

    # Determine render mode
    _mode = mode
    if _mode is None:
        _mode = 'cmdline' if dcc.batch_mode() else 'mel'
    _LOGGER.info(' - RENDER MODE %s', _mode)

    # Prepare output path
    if seq.exists(frames=_frames):
        _LOGGER.info(' - CUR FRAMES %s', seq.to_range())
        seq.delete(wording='Replace', icon=icons.find('Sponge'), frames=_frames)

    # Execute render
    if _mode in ['api', 'mel']:
        for _frame in qt.progress_bar(
                _frames, 'Rendering {:d} frame{}'):
            check_heart()
            cmds.currentTime(_frame)
            render_frame(
                file_=File(seq[_frame]), camera=camera,
                pre_frame_mel=pre_frame_mel, post_frame_mel=post_frame_mel,
                pre_frame=pre_frame, post_frame=post_frame)
        assert seq.exists(force=True)
    elif _mode == 'cmdline':
        if pre_frame or post_frame:
            raise NotImplementedError
        _exec_cmdline_render(
            seq=seq, camera=camera, frames=_frames, pre_frame_mel=pre_frame_mel,
            verbose=verbose, post_frame_mel=post_frame_mel)
    else:
        raise ValueError(_mode)

    assert seq.exists()
    if view:
        seq.view()


def set_render_extn(extn):
    """Set render format for the current renderer.

    Args:
        extn (str): format to apply
    """
    _ren = cmds.getAttr('defaultRenderGlobals.currentRenderer')
    if _ren == 'vray':
        cmds.setAttr("vraySettings.imageFormatStr", extn, type='string')
        return
    raise NotImplementedError(_ren)


def to_render_extn():
    """Read render extension based on current renderer.

    Returns:
        (str): render extn (eg. jpg/exr)
    """
    _ren = cmds.getAttr('defaultRenderGlobals.currentRenderer')
    _fmt = None
    if _ren == 'arnold':
        if cmds.objExists('defaultArnoldDriver'):
            _fmt = cmds.getAttr('defaultArnoldDriver.aiTranslator')
            if _fmt == 'jpeg':
                _fmt = 'jpg'

    elif _ren == 'vray':
        if cmds.objExists('vraySettings'):
            _fmt = cmds.getAttr("vraySettings.imageFormatStr")

    elif _ren == 'redshift':
        _image = single(cmds.renderSettings(firstImageName=True))
        _fmt = File(_image).extn

    elif _ren == 'mayaSoftware':
        if cmds.objExists('defaultRenderGlobals'):
            _fmt = cmds.getAttr(
                'defaultRenderGlobals.imageFormat', asString=True)
            _fmt = _fmt.lower()

    else:
        _LOGGER.warning('Renderer not implemented %s', _ren)

    # Fix description in attr name (eg. "exr (multichannel)")
    if _fmt:
        _fmt = _fmt.split()[0]

    return _fmt
