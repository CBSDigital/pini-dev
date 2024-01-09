"""General pini helper utils."""

import logging

import six

from pini import icons, qt, pipe, dcc
from pini.utils import str_to_seed, cache_result, Seq, Video

_LOGGER = logging.getLogger(__name__)

CURRENT_ICON = icons.find('Star')
UPDATE_ICON = icons.find('Gear')

ABC_ICON = icons.find('Input Latin Letters')
ABC_BG_ICON = icons.find('Blue Square')
ASS_ICON = icons.find('Peach')
BLAST_ICON = icons.find('Collision')
CAM_ICON = icons.find('Movie Camera')
CSET_ICON = icons.find('Urn')
LOOKDEV_BG_ICON = icons.find('Green circle')
LOOKDEV_ICON = icons.find('Palette')
MISSING_FROM_CACHE_ICON = icons.find('Adhesive Bandage')
MODEL_ICON = icons.find('Ice')
PLATE_ICON = icons.find('Plate')
RENDER_ICON = icons.find('Film Frames')
RIG_ICON = icons.find('Bone')
USD_ICON = icons.find('Milky Way')
VDB_ICON = icons.find('Cloud')
VIDEO_ICON = icons.find('Videocassette')

EXTN_ICONS = {
    'abc': ABC_ICON,
    'ass': ASS_ICON,
    'vdb': VDB_ICON,
    'usd': USD_ICON,
}
_TYPE_BG_MAP = {
    'render': icons.find('Red Circle'),
    'render_mov': icons.find('Orange Circle'),
    'blast': icons.find('Yellow Circle'),
    'blast_mov': icons.find('Yellow Circle'),
}

_CACHE_ICONS = icons.EMOJI.find_grp('FRUIT')
_WORK_ICONS = icons.EMOJI.find_grp('COOL')
_8_BALL_ICON = icons.find('Pool 8 Ball')

_NAME_MAP = {
    'bottle': 'Bottle with Popping Cork',
    'chesspieces': 'Chess Pawn',
    'christmaspresents': 'Gift',
    'clouds': 'Cloud',
    'coins': 'Money Bag',
    'discoball': 'Crystal Ball',
    'eggs': 'Egg',
    'ferns': 'Potted Plant',
    'ground': 'Desert',
    'hand': 'Waving Hand: Medium Skin Tone',
    'lamppost': 'Light Bulb',
    'lightrig': 'Light Bulb',
    'kitchencounter': 'Fork and Knife with Plate',
    'moon': 'Last Quarter Moon Face',
    'musicalnotes': 'Musical Note',
    'musicnotes': 'Musical Note',
    'palms': "Palm Tree",
    'personm': "Men's Room",
    'personf': "Women's Room",
    'rocketship': 'Rocket',
    'screen': 'Television',
    'snowflakes': 'Snowflake',
    'snowflakesice': 'Cloud with Snow',
    'spacesky': 'Milky Way',
    'spacestation': 'Satellite',
    'speakers': 'Loudspeaker',
    'whiteclouds': 'Cloud',
    'xmastrees': 'Christmas Tree',
}


def is_active():
    """Test whether the pini helper is currently active.

    Returns:
        (bool): whether pini helper is open and visible
    """
    from pini.tools import helper
    try:
        return bool(helper.DIALOG and helper.DIALOG.isVisible())
    except RuntimeError:
        return False


def _abc_to_icon(abc):
    """Obtain icon for abc output.

    Args:
        abc (CPOutput): abc output

    Returns:
        (str|QPixmap): icon
    """
    _type = abc.metadata.get('type')
    _asset_path = abc.metadata.get('asset')

    # Find overlay path
    _over_path = None
    if _asset_path:
        _asset = pipe.CPOutput(pipe.map_path(_asset_path))
        _over_path = output_to_icon(_asset)
    elif _type == 'CPCacheableCam':
        _over_path = CAM_ICON
    elif _type == 'CPCacheableSet':
        _over_path = CSET_ICON

    # Build icon
    if _over_path:
        _icon = _add_icon_overlay(
            ABC_BG_ICON, overlay=_over_path, mode='C')
    else:
        _icon = ABC_ICON

    return _icon


def _lookdev_to_icon(lookdev):
    """Obtain icon for lookdev asset.

    Args:
        lookdev (CPOutuput): lookdev publish

    Returns:
        (CPixmap): icon
    """
    assert lookdev.type_ == 'publish'
    assert lookdev.output_type == 'lookdev'

    # Find rig icon
    _tmpl = lookdev.job.find_template('publish', has_key={
        'output_type': False, 'ver': False, 'tag': bool(lookdev.tag)})
    _rig_out = lookdev.to_output(task='rig', template=_tmpl)
    # print _rig_out
    _asset_icon = output_to_icon(_rig_out)

    _icon = qt.CPixmap(LOOKDEV_BG_ICON)
    _over = qt.CPixmap(_asset_icon)
    _icon.draw_overlay(
        _over, pos=_icon.center(), size=_over.size()*0.6, anchor='C')

    return _icon


def _output_to_rand_icon(output):
    """Map output to a random icon.

    Args:
        output (CPOutput): output to map

    Returns:
        (str): path to icon
    """

    # Try to match with mapped icon
    _ety = output.entity
    _ety_name = output.entity.name
    while _ety_name and _ety_name[-1].isdigit():
        _ety_name = _ety_name[:-1]
    _name = _NAME_MAP.get(_ety_name.lower(), _ety_name)
    _icon = icons.find(_name, catch=True)

    # Determine icon path
    if _icon:
        _NAME_MAP[_name] = _icon
    else:
        if _ety.profile == 'asset':
            _uid = _ety.path
        elif _ety.profile == 'shot':
            _uid = output.to_output(ver_n=0).path
        else:
            raise ValueError(_ety)
        _rand = str_to_seed(_uid)
        _icon = _rand.choice(_CACHE_ICONS)

    return _icon


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
    if isinstance(_overlay, six.string_types) and '/' not in _overlay:
        _overlay = icons.find(_overlay)

    # Build pixmap
    _icon = qt.CPixmap(icon)
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
def obt_icon_pixmap(path, size):
    """Obtain pixmap for the given icon/size, resuing existing icons.

    Args:
        path (str): path to pixmap
        size (int): icon size

    Returns:
        (QPixmap): icon
    """
    _pix = qt.CPixmap(path)
    _pix = _pix.resize(size)
    return _pix


@cache_result
def output_to_icon(output, overlay=None):
    """Obtain an icon for the given output.

    Args:
        output (CPOutput): output to find icon for
        overlay (str): name of overlay emoji to apply to bottom left

    Returns:
        (CPixmap): icon
    """
    assert isinstance(output, (pipe.CPOutput, pipe.CPOutputSeq))

    # Get base icon
    _bg = None
    if output.extn == 'abc':
        _icon = _abc_to_icon(output)
    elif output.output_type == 'cam':
        _icon = CAM_ICON
    elif output.asset_type == 'utl' and output.asset == 'camera':
        _icon = CAM_ICON
    elif output.asset_type == 'utl' and output.asset == 'lookdev':
        _icon = LOOKDEV_ICON
    elif output.type_ == 'publish' and output.output_type == 'lookdev':
        _icon = _lookdev_to_icon(output)
    elif output.type_ in _TYPE_BG_MAP:
        _bg = _TYPE_BG_MAP[output.type_]
        _icon = _output_to_rand_icon(output)
    else:
        _icon = _output_to_rand_icon(output)

    if overlay:
        _icon = _add_icon_overlay(icon=_icon, overlay=overlay)
    if _bg:
        _icon = _add_icon_overlay(icon=_bg, overlay=_icon, mode='C')

    return _icon


def output_to_namespace(output, attach=None, ignore=(), base=None):
    """Get namespace for the given output.

    Args:
        output (CPOutput): output being referenced
        attach (CPOutput): target output which this output is being
            attached to (eg. lookdev attach to abc)
        ignore (str list): namespaces to ignore (ie. namespaces which
            have already be allocated for staged imports)
        base (str): override namespace base

    Returns:
        (str): namespace for this output
    """
    if attach:
        return attach.namespace+'_shd'

    _mode = 'asset'
    if base:
        _base = base
    elif output.type_ in ['publish']:
        _base = output.entity.name

    elif output.type_ == 'cache' and output.output_type == 'cam':
        _mode = 'cache'
        _base = '{}_{}'.format(output.entity.name, output.output_name)
    elif output.type_ == 'cache' and output.output_name == 'restCache':
        _base = output.entity.name
    elif output.type_ in ['cache', 'cache_seq', 'ass_gz']:
        _mode = 'cache'
        _base = output.output_name

    elif isinstance(output, (Seq, Video)):
        _ver = 'v{:03d}'.format(output.ver_n)
        _base = output.base.replace(_ver, '').strip('_')
    else:
        _LOGGER.info(' - TYPE %s', output.type_)
        raise ValueError(output)

    _ns = dcc.get_next_namespace(_base, ignore=ignore, mode=_mode)
    _ns = _ns.strip(':')
    return _ns


def output_to_type_icon(output):
    """Obtain type icon for the given output.

    Args:
        output (CPOutput): output to get icon for

    Returns:
        (str): path to icon
    """
    if output.nice_type == 'render':
        return RENDER_ICON
    if output.nice_type == 'plate':
        return PLATE_ICON
    if output.nice_type == 'blast':
        return BLAST_ICON

    if output.extn in EXTN_ICONS:
        return EXTN_ICONS[output.extn]

    return {'model': MODEL_ICON,
            'rig': RIG_ICON,
            'lookdev': LOOKDEV_ICON}.get(output.task)


def work_to_icon(work):
    """Obtain icon for the given work file.

    Args:
        work (CPWork): work to obtain icon for

    Returns:
        (str): path to icon
    """
    if work.ver_n == 8:
        return _8_BALL_ICON
    _icons = _WORK_ICONS[:]
    str_to_seed(work.work_dir.path+str(work.tag)).shuffle(_icons)
    return _icons[work.ver_n % len(_icons)]
