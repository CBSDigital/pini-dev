"""Tools for managing flipbooking."""

import logging
import os

import toolutils  # pylint: disable=import-error

from pini import pipe, dcc
from pini.dcc import export
from pini.tools import error, usage
from pini.utils import find_exe, find_viewer, TMP

from hou_pini.utils import flipbook as u_flipbook

_LOGGER = logging.getLogger(__name__)


def _prepare_output_path(format_, force):
    """Prepare flipbook sequence and output path based on format.

    Args:
        format_ (str): output format (eg. mp4/jpg)
        force (bool): replace existing without confirmation

    Returns:
        (tuple): flipbook sequence, output, video conversion
            required, flipbook viewer
    """
    _work = pipe.CACHE.cur_work

    if not _work:
        raise error.HandledError('No current work file found.')

    _to_video = False
    if format_ in ['mp4', 'mov']:
        _seq = TMP.to_seq('pini/houBlast/tmp.%04d.jpg')
        _seq.delete(force=True)
        _out = _work.to_output(
            'blast_mov', extn=format_, output_name='flipbook')
        _viewer = find_viewer(plays_videos=True)
        _to_video = True
    elif format_ in ['png', 'jpg']:
        _seq = _work.to_output(
            'blast', extn=format_, output_name='flipbook')
        _out = _seq
        _viewer = find_viewer('mplay')
    else:
        raise ValueError(format_)
    _LOGGER.info(' - BLAST SEQ %s', _seq)
    _LOGGER.info(' - BLAST OUT %s', _out)

    _out.delete(force=force, wording='Replace')

    return _seq, _out, _to_video, _viewer


@usage.get_tracker('HouFlipbook')
@error.catch
def flipbook(
        format_=None, view=True, range_=None, burnins=False, save=True,
        force=False):
    """Execute flipbook.

    Args:
        format_ (str): flipbook format
        view (bool): view flipbook on completion
        range_ (tuple): override flipbook range start/end
        burnins (bool): apply burnins
        save (bool): save scene on flipbook
        force (bool): replace existing without confirmation
    """
    _LOGGER.info('FLIPBOOK %s', format_)

    _fmt = os.environ.get('PINI_VIDEO_FORMAT', 'mp4')
    _seq, _out, _to_video, _viewer = _prepare_output_path(
        format_=_fmt, force=force)
    _LOGGER.info(' - OUT %s', _out)

    _mplay = find_exe('mplay')
    _LOGGER.info(' - MPLAY %s', _mplay)
    _sv = toolutils.sceneViewer()  # NOTE: this call seems to crash logging
    _LOGGER.info(' - VIEWER %s', _sv)
    _vp = _sv.curViewport()
    _LOGGER.info(' - VIEWPORT %s', _vp)
    _cam = _vp.camera()
    _work = pipe.CACHE.obt_cur_work()
    _fps = dcc.get_fps()
    _LOGGER.info(' - CAM %s', _cam)
    _bkp = None
    if save:
        _bkp = _work.save(reason='blast', result='bkp')
    _data = export.build_metadata('Flipbook', work=_work, bkp=_bkp)
    u_flipbook(_seq, force=True, view=False, range_=range_)

    # Post processing
    if _to_video:
        _LOGGER.info(' - MAKING MOV %s %s', format_, _out)
        _seq.to_video(_out, fps=_fps, burnins=burnins)
        _seq.delete(force=True)
        _thumb = TMP.to_file('pini/tmp.jpg')
        _out.to_frame(_thumb, force=True)
    else:
        _thumb = _seq.to_frame_file()
    _thumb.copy_to(_work.image, force=True)
    if view:
        _LOGGER.info(' - MPLAY %s', _mplay)
        _viewer.view(_out)
    _out.set_metadata(_data, force=True)
    if pipe.MASTER == 'shotgrid':
        from pini.pipe import shotgrid
        shotgrid.create_pub_file_from_output(
            _out, thumb=_thumb, status='ip', force=True)

    _work.update_outputs()
