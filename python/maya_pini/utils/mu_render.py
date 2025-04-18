"""Utilities for rendering."""

import collections
import functools
import logging
import time

from maya import cmds, mel

from pini import icons
from pini.utils import File, single, find_exe, system, check_heart, Res

_LOGGER = logging.getLogger(__name__)
_REN_FMTS_MAP = {}


def _revert_render_window(func):
    """Decorator to revert render window .

    Args:
        func (fn): function to decorate

    Returns:
        (fn): decorated function
    """

    @functools.wraps(func)
    def _revert_render_window_func(*args, **kwargs):
        _win = cmds.window('renderViewWindow', query=True, exists=True)
        _result = func(*args, **kwargs)
        if not _win and cmds.window(
                'renderViewWindow', query=True, exists=True):
            cmds.deleteUI('renderViewWindow')
        return _result

    return _revert_render_window_func


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
                 f"{path.dir}/{path.base}", type='string')
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
            res[0], res[1], True, True, cam, ' -layer ' + layer)
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
        _tmp_file = file_.to_file(base=file_.base + '_1')
        if not _tmp_file.exists():
            _LOGGER.info(' - FILE %s', file_)
            _LOGGER.info(' - TMP FILE %s', _tmp_file)
            raise RuntimeError(f'Missing file {file_}')
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


@_revert_render_window
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
        seq.delete(wording='replace', icon=icons.find('Sponge'), frames=_frames)

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


def _obt_image_fmts_map():
    """Obtain image formats map for the current renderer.

    This applies all available int values to the image format attribute
    and tests what the image format extension is after it's applied.

    Returns:
        (dict): map of index to format name
    """
    _ren = cmds.getAttr('defaultRenderGlobals.currentRenderer')
    if _ren not in _REN_FMTS_MAP:
        _fmts = collections.defaultdict(list)
        if _ren == 'mayaSoftware':
            _lle = cmds.attributeQuery(
                'imageFormat', node='defaultRenderGlobals',
                localizedListEnum=True)
            _idxs = [int(_item.rsplit('=', 1)[1]) for _item in _lle]
            for _idx in _idxs:
                cmds.setAttr('defaultRenderGlobals.imageFormat', _idx)
                _extn = to_render_extn()
                _LOGGER.debug(' - EXTN %d %s', _idx, _extn)
                _fmts[_extn].append(_idx)
        elif _ren == 'redshift':
            _val = cmds.getAttr('redshiftOptions.imageFormat')
            for _idx in range(10):
                _apply_rs_fmt_idx(_idx)
                _extn = to_render_extn()
                _LOGGER.debug(' - IDX %d %s', _idx, _extn)
                if not _extn or _extn in _fmts:
                    break
                _fmts[_extn].append(_idx)
            cmds.setAttr('redshiftOptions.imageFormat', _val)
            mel.eval('redshiftImageFormatChanged')
        else:
            raise ValueError(_ren)
        _fmts = dict(_fmts)
        _REN_FMTS_MAP[_ren] = _fmts
    return _REN_FMTS_MAP[_ren]


def _apply_rs_fmt_idx(idx):
    """Apply a redshift image format index update.

    Args:
        idx (int): index to apply
    """
    cmds.setAttr('redshiftOptions.imageFormat', idx)
    try:
        mel.eval('redshiftImageFormatChanged')
    except RuntimeError as _exc:
        raise RuntimeError(
            'Update image format failed - this could be because '
            'render globals window needs to be opened to initialise '
            'redshift') from _exc


def set_render_extn(extn: str):
    """Set render format for the current renderer.

    Args:
        extn (str): format to apply
    """
    from maya_pini import open_maya as pom
    from maya_pini.utils import process_deferred_events

    # Apply extn
    _ren = cmds.getAttr('defaultRenderGlobals.currentRenderer')
    if _ren == 'arnold':
        process_deferred_events()
        pom.CPlug('defaultArnoldDriver.aiTranslator').set_val(extn)
    elif _ren == 'mayaSoftware':
        _map = _obt_image_fmts_map()
        _idx = single(_map[extn])
        cmds.setAttr('defaultRenderGlobals.imageFormat', _idx)
        _LOGGER.info(' - SET defaultRenderGlobals.imageFormat %s', _idx)
    elif _ren == 'redshift':
        _map = _obt_image_fmts_map()
        _idx = single(_map[extn])
        _apply_rs_fmt_idx(_idx)
    elif _ren == 'vray':
        cmds.setAttr("vraySettings.imageFormatStr", extn, type='string')
    else:
        raise NotImplementedError(_ren)

    # Check success
    _extn = to_render_extn()
    if _extn != extn:
        raise RuntimeError(
            f'Failed to apply extn "{extn}" (currently "{_extn}")')


def set_render_res(res: tuple):
    """Set render resolution.

    Args:
        res (tuple): width/height to apply
    """
    _ren = cmds.getAttr('defaultRenderGlobals.currentRenderer')
    if _ren in ('mayaSoftware', 'redshift', 'arnold'):
        cmds.setAttr('defaultResolution.width', res[0])
        cmds.setAttr('defaultResolution.height', res[1])
    elif _ren == 'vray':
        cmds.setAttr('vraySettings.width', res[0])
        cmds.setAttr('vraySettings.height', res[1])
    else:
        raise NotImplementedError(_ren)


def to_render_extn():
    """Read render extension based on current renderer.

    Returns:
        (str): render extn (eg. jpg/exr)
    """
    _ren = cmds.getAttr('defaultRenderGlobals.currentRenderer')
    _LOGGER.debug('TO RENDER EXTN %s', _ren)
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
        _LOGGER.debug(' - IMG %s', _image)
        _, _fmt = _image.rsplit('.', 1)

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
    _LOGGER.debug(' - FMT %s', _fmt)

    return _fmt


def to_render_res(name=None):
    """Get current render resolution.

    Args:
        name (str): apply resolution name

    Returns:
        (Res): render resolution
    """
    _ren = cmds.getAttr('defaultRenderGlobals.currentRenderer')
    if _ren in ('arnold', 'mayaSoftware', 'redshift'):
        _res_x, _res_y = (
            cmds.getAttr(f'defaultResolution.{_attr}')
            for _attr in ['width', 'height'])
    elif _ren == 'vray':
        _res_x, _res_y = (
            cmds.getAttr(f'vraySettings.{_attr}')
            for _attr in ['width', 'height'])
    else:
        raise NotImplementedError(_ren)
    return Res(_res_x, _res_y, name=name)
