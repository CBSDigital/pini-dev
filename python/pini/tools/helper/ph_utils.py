"""General pini helper utils."""

import logging

from pini import icons, qt, pipe, dcc
from pini.pipe import cache
from pini.qt import QtGui
from pini.utils import (
    str_to_seed, cache_result, Seq, Video, File, to_str, find_callback)

_LOGGER = logging.getLogger(__name__)

CURRENT_ICON = icons.find('Star')
UPDATE_ICON = icons.find('Gear')

ABC_ICON = icons.find('Input Latin Letters')
ASS_ICON = icons.find('Peach')
CAM_ICON = icons.find('Movie Camera')
CSET_ICON = icons.find('Urn')
FBX_ICON = icons.find('Worm')
IMG_FILE_ICON = icons.find('Framed Picture')
MAYA_FILE_ICON = icons.find('Moai')
MISSING_FROM_CACHE_ICON = icons.find('Adhesive Bandage')
NUKE_FILE_ICON = icons.find('Radioactive')
USD_ICON = icons.find('Milky Way')
VDB_ICON = icons.find('Cloud')
VIDEO_ICON = icons.find('Videocassette')

ABC_BG_ICON = icons.find('Blue Square')
CURVES_MB_BG_ICON = icons.find('Yellow Circle')
FBX_BG_ICON = icons.find('Green Square')
LOOKDEV_BG_ICON = icons.find('Green Circle')
RS_BG_ICON = icons.find('Red Circle')
VRMESH_BG_ICON = icons.find('Orange Circle')

ARCHIVE_TYPE_ICON = icons.find('Red Paper Lantern')
DEFAULT_ICON = icons.find('Black Medium-Small Square')
DEFAULT_BASE_ICON = icons.find('White Large Square')
BLAST_TYPE_ICON = icons.find('Collision')
CURVES_TYPE_ICON = icons.find('Performing Arts')
LOOKDEV_TYPE_ICON = icons.find('Palette')
MODEL_TYPE_ICON = icons.find('Ice')
PLATE_TYPE_ICON = icons.find('Plate')
RENDER_TYPE_ICON = icons.find('Film Frames')
RIG_TYPE_ICON = icons.find('Bone')
RS_TYPE_ICON = icons.find('Police Car Light')

EXTN_ICONS = {
    'abc': ABC_ICON,
    'ass': ASS_ICON,
    'fbx': FBX_ICON,
    'ma': MAYA_FILE_ICON,
    'mb': MAYA_FILE_ICON,
    'nk': NUKE_FILE_ICON,
    'vdb': VDB_ICON,
    'usd': USD_ICON,
}
_EXTN_BG_MAP = {
    'abc': ABC_BG_ICON,
    'fbx': FBX_BG_ICON,
}
_TYPE_BG_MAP = {
    'plate': icons.find('Brown Circle'),
    'render': icons.find('Red Circle'),
    'render_mov': icons.find('Orange Circle'),
    'blast': icons.find('Yellow Circle'),
    'blast_mov': icons.find('Yellow Circle'),
}

_CACHE_ICONS = icons.EMOJI.find_grp('FRUIT')
_WORK_ICONS = icons.EMOJI.find_grp('COOL')
_8_BALL_ICON = icons.find('Pool 8 Ball')
_NO_CACHE_OUTPUT_ICON = icons.find('White Circle')
_NO_CACHE_TYPE_ICON = icons.find('Cross Mark')

_ICON_CACHE = {}


def is_active():
    """Test whether the pini helper is currently active.

    Returns:
        (bool): whether pini helper is open and visible
    """
    _LOGGER.debug('IS ACTIVE')
    from pini.tools import helper
    if not helper.DIALOG:
        _LOGGER.debug(' - MISSING GLOBAL')
        return False
    try:
        _active = helper.DIALOG.is_active()
    except RuntimeError:
        _LOGGER.debug(' - ERRORED READING ACTIVE')
        return False
    _LOGGER.debug(' - ACTIVE %d', _active)
    return _active


def obt_helper(reset_cache=False):
    """Obtaion helper dialog, launching if needed.

    Args:
        reset_cache (bool): reset cache on launch

    Returns:
        (PiniHelper): helper instance
    """
    _LOGGER.debug('OBT HELPER %d', reset_cache)
    from pini.tools import helper
    if not helper.is_active():
        _LOGGER.debug(' - LAUNCHING HELPER')
        helper.launch(reset_cache=reset_cache)
    return helper.DIALOG


def _cache_to_icon(output):
    """Obtain icon for cache output.

    Args:
        output (CPOutput): cache

    Returns:
        (str|QPixmap): icon
    """

    # Find overlay path (eg. icon from from a source entity)
    _over_path = None
    if output.src_ref:
        _asset = pipe.CPOutputFile(output.src_ref)
        _over_path = output_to_icon(_asset)
    elif output.content_type == 'CameraAbc' or output.task == 'cam':
        _over_path = CAM_ICON
    elif output.type_ == 'CPCacheableSet':
        _over_path = CSET_ICON
    else:
        _over_path = DEFAULT_ICON
    _LOGGER.debug(' - OVER PATH %s', _over_path)

    # Determine base icon
    if _over_path:
        _base_icon = (
            _EXTN_BG_MAP.get(output.extn) or
            DEFAULT_BASE_ICON)
        _LOGGER.debug(' - BASE ICON extn=%s %s', output.extn, _base_icon)
        _icon = _add_icon_overlay(_base_icon, overlay=_over_path, mode='C')
    else:
        _icon = None
        if output.pini_task == 'cam':
            _icon = CAM_ICON
        if not _icon:
            _icon = DEFAULT_ICON
        _LOGGER.debug(' - ICON task=%s %s', output.pini_task, _icon)

    return _icon


def _curves_to_icon(curves):
    """Build icons for CurveMa/CurveMb outputs.

    Args:
        curves (CPOutput): output to build icon for

    Returns:
        (CPixmap): icon
    """
    _base_icon = CURVES_MB_BG_ICON
    _asset_icon = None
    _asset = curves.metadata.get('src_ref')
    if _asset:
        _asset_out = pipe.CACHE.obt_output(_asset)
        _asset_icon = _output_to_entity_icon(_asset_out)

    _icon = qt.CPixmap(_base_icon)
    _over = qt.CPixmap(_asset_icon)
    _icon.draw_overlay(
        _over, pos=_icon.center(), size=_over.size() * 0.6, anchor='C')

    return _icon


def _lookdev_to_icon(lookdev):
    """Obtain icon for lookdev asset.

    Args:
        lookdev (CPOutuput): lookdev publish

    Returns:
        (CPixmap): icon
    """
    _LOGGER.debug(' - LOOKDEV TO ICON %s', lookdev)
    assert lookdev.type_ in ('publish', 'publish_seq')

    _asset_icon = _output_to_entity_icon(lookdev)

    if lookdev.content_type == 'VrmeshMa':
        _base_icon = VRMESH_BG_ICON
    elif lookdev.content_type == 'RedshiftProxy':
        _base_icon = RS_BG_ICON
    elif lookdev.content_type == 'ShadersMa':
        _base_icon = LOOKDEV_BG_ICON
    else:
        raise ValueError(lookdev, lookdev.content_type)

    _icon = qt.CPixmap(_base_icon)
    _over = qt.CPixmap(_asset_icon)
    _icon.draw_overlay(
        _over, pos=_icon.center(), size=_over.size() * 0.6, anchor='C')

    return _icon


def _output_to_entity_icon(output):
    """Map output to a random icon.

    Args:
        output (CPOutput): output to map

    Returns:
        (str): path to icon
    """
    if isinstance(output, cache.CCPOutputBase):
        _ety = output.entity
    elif isinstance(output, cache.CCPOutputGhost):
        _ety = pipe.CACHE.obt_entity(output.path)
    else:
        raise ValueError(output)
    return _ety.to_icon()


def _add_icon_overlay(icon, overlay, mode='BL'):
    """Add overlay to the given icon.

    Args:
        icon (str): path to icon to overlay
        overlay (str): path to overlay to add
        mode (str): overlay mode
            BL (default) - add to bottom left
            C - add to centre (for square/circle backdrop)

    Returns:
        (CPixmap): icon with overlay
    """

    # Obtain overlay path
    _overlay = overlay
    if isinstance(_overlay, str) and '/' not in _overlay:
        _overlay = icons.find(_overlay)

    # Build pixmap
    _icon = icon
    if not isinstance(_icon, QtGui.QPixmap):
        _icon = qt.obt_pixmap(_icon)
    _over_scale = 0.6
    _over_size = _icon.size() * _over_scale
    if mode == 'BL':
        _margin = 0
        _pos = qt.to_p(_margin, _icon.height() - _margin)
        _icon.draw_overlay(
            _overlay, size=_over_size, pos=_pos, anchor='BL')
    elif mode == 'C':
        _icon.draw_overlay(
            _overlay, pos=_icon.center(), size=_over_size, anchor='C')
    else:
        raise NotImplementedError(mode)

    return _icon


@cache_result
def obt_pixmap(file_, size=None, force=False):
    """Obtain pixmap for the given icon/size, resuing existing icons.

    Args:
        file_ (str): image file to read
        size (int): icon size
        force (bool): force reread item from disk

    Returns:
        (QPixmap): icon
    """
    _file = File(file_)
    _pix = qt.to_pixmap(_file)
    if size:
        _pix = _pix.resize(size)
    return _pix


@cache_result
def obt_recent_work(force=False):
    """Obtain recent work list.

    Args:
        force (bool): force reread from disk

    Returns:
        (CPWork list): recent work files
    """
    return pipe.recent_work()


@cache_result
def output_to_icon(output, overlay=None, force=False):  # pylint: disable=too-many-branches
    """Obtain an icon for the given output.

    Args:
        output (CPOutput): output to find icon for
        overlay (str): name of overlay emoji to apply to bottom left
        force (bool): force rebuild icon

    Returns:
        (CPixmap): icon
    """
    _LOGGER.debug('OUTPUT TO ICON %s over=%s force=%d', output, overlay, force)
    _LOGGER.debug(' - BASIC TYPE %s', output.basic_type)

    # Get base icon
    if not isinstance(output, (cache.CCPOutputBase, cache.CCPOutputGhost)):
        _icon = _NO_CACHE_OUTPUT_ICON

    else:

        _bg = None
        if output.content_type == 'CurvesMb':
            _LOGGER.debug(' - APPLYING CURVES MB ICON')
            _icon = _curves_to_icon(output)
        elif output.basic_type == 'cache':
            _LOGGER.debug(' - APPLYING CACHE ICON')
            _icon = _cache_to_icon(output)
        elif output.output_type == 'cam':
            _icon = CAM_ICON
        elif output.asset_type == 'utl' and output.asset == 'camera':
            _icon = CAM_ICON
        elif output.asset_type == 'utl' and output.asset == 'lookdev':
            _icon = LOOKDEV_TYPE_ICON
        elif (
                output.type_ in ('publish', 'publish_seq') and
                output.pini_task == 'lookdev' and
                output.content_type in (
                    'ShadersMa', 'VrmeshMa', 'RedshiftProxy')):
            _LOGGER.debug(' - APPLYING LOOKDEV ICON')
            _icon = _lookdev_to_icon(output)
        elif output.type_ in _TYPE_BG_MAP:
            _bg = _TYPE_BG_MAP[output.type_]
            _icon = _output_to_entity_icon(output)
        else:
            _LOGGER.debug(' - APPLYING ENTITY ICON')
            _icon = _output_to_entity_icon(output)

        if overlay:
            _icon = _add_icon_overlay(icon=_icon, overlay=overlay)
        if _bg:
            _icon = _add_icon_overlay(icon=_bg, overlay=_icon, mode='C')

    _LOGGER.debug(' - ICON %s', _icon)
    if _icon and not isinstance(_icon, QtGui.QPixmap):
        _icon = qt.obt_pixmap(to_str(_icon))
        assert isinstance(_icon, QtGui.QPixmap)

    return _icon


def output_to_namespace(output, attach_to=None, ignore=(), base=None):
    """Get namespace for the given output.

    Args:
        output (CPOutput): output being referenced
        attach_to (CPOutput): target output which this output is being
            attached to (eg. lookdev attach to abc)
        ignore (str list): namespaces to ignore (ie. namespaces which
            have already be allocated for staged imports)
        base (str): override namespace base

    Returns:
        (str): namespace for this output
    """
    if attach_to:
        return attach_to.namespace + '_shd'

    _mode = 'asset'
    _ety_name = output.asset or output.shot
    if base:
        _base = base
    elif output.type_ in ('publish', 'publish_seq'):
        _base = _ety_name
    elif output.type_ == 'cache' and output.output_type == 'cam':
        _mode = 'cache'
        _base = f'{_ety_name}_{output.output_name}'
    elif output.type_ == 'cache' and output.output_name == 'restCache':
        _base = _ety_name
    elif output.type_ in ['cache', 'cache_seq', 'ass_gz']:
        _mode = 'cache'
        _base = output.output_name or _ety_name
    elif isinstance(output, (Seq, Video)):
        _ver = f'v{output.ver_n:03d}'
        _base = output.base.replace(_ver, '').strip('_')
    else:
        _LOGGER.info(' - TYPE %s', output.type_)
        raise ValueError(output)

    _ns = dcc.get_next_namespace(_base, ignore=ignore, mode=_mode)
    _ns = _ns.strip(':')
    return _ns


def output_to_type_icon(output):  # pylint: disable=too-many-return-statements
    """Obtain type icon for the given output.

    Args:
        output (CPOutput): output to get icon for

    Returns:
        (str): path to icon
    """
    _LOGGER.debug('OUTPUT TO TYPE ICON %s', output)
    if not isinstance(output, (cache.CCPOutputBase, cache.CCPOutputGhost)):
        return _NO_CACHE_TYPE_ICON
    _LOGGER.debug(
        ' - BASIC/CONTENT TYPES %s %s', output.basic_type, output.content_type)
    if output.basic_type == 'render':
        return RENDER_TYPE_ICON
    if output.basic_type == 'plate':
        return PLATE_TYPE_ICON
    if output.basic_type == 'blast':
        return BLAST_TYPE_ICON
    if output.content_type == 'VrmeshMa':
        return ARCHIVE_TYPE_ICON
    if output.content_type == 'RedshiftProxy':
        return RS_TYPE_ICON
    if output.content_type in ['CurvesMa', 'CurvesMb']:
        return CURVES_TYPE_ICON
    if output.content_type == 'BasicMa':
        return MAYA_FILE_ICON
    if output.content_type == 'Image':
        return IMG_FILE_ICON

    if (
            output.extn not in ('ma', 'mb') and
            output.extn in EXTN_ICONS):
        return EXTN_ICONS[output.extn]

    _task_map = {
        'model': MODEL_TYPE_ICON,
        'rig': RIG_TYPE_ICON,
        'lookdev': LOOKDEV_TYPE_ICON}
    _step = pipe.map_task(output.step)
    _task = pipe.map_task(output.task)
    return _task_map.get(_step) or _task_map.get(_task)


def _basic_work_icon(work):
    """Basic work to icon function.

    Args:
        work (CCPWork): work file to read icon for

    Returns:
        (CPixmap): icon pixmap
    """
    if work.ver_n == 8:
        return _8_BALL_ICON
    _icons = list(_WORK_ICONS)
    str_to_seed(work.work_dir.path + str(work.tag)).shuffle(_icons)
    return _icons[work.ver_n % len(_icons)]


@cache_result
def work_to_icon(work):
    """Obtain icon for the given work file.

    Args:
        work (CPWork): work to obtain icon for

    Returns:
        (str): path to icon
    """
    _callback = find_callback('HelperWorkIcon')
    if _callback:
        return _callback(work)
    return _basic_work_icon(work)
