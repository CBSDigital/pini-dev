"""Tools for managing flipbooking."""

import logging

import toolutils  # pylint: disable=import-error

from pini import pipe, dcc
from pini.tools import error, usage
from pini.utils import Dir, TMP_PATH, find_exe, find_viewer, Seq

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

    assert _work
    _to_video = False
    if format_ in ['mp4']:
        _seq = Seq(Dir(TMP_PATH).to_file('pini/houBlast/tmp.%04d.jpg'))
        _seq.delete(force=True)
        _out = _work.to_output('blast_mov', extn=format_)
        _viewer = find_viewer(plays_videos=True)
        _to_video = True
    elif format_ in ['png', 'jpg']:
        _seq = _work.to_output('blast', extn=format_)
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
def flipbook(format_='mp4', view=True, range_=None, burnins=False, force=False):
    """Execute flipbook.

    Args:
        format_ (str): flipbook format
        view (bool): view flipbook on completion
        range_ (tuple): override flipbook range start/end
        burnins (bool): apply burnins
        force (bool): replace existing without confirmation
    """
    _LOGGER.info('FLIPBOOK')

    _mplay = find_exe('mplay')
    _sv = toolutils.sceneViewer()
    _vp = _sv.curViewport()
    _cam = _vp.camera()
    _work = pipe.CACHE.cur_work
    _fps = dcc.get_fps()
    _LOGGER.info(' - CAM %s', _cam)

    # Determine range
    if range_:
        _rng = range_
    else:
        _rng = dcc.t_range()
    _LOGGER.info(' - RANGE %d-%d', *_rng)

    _seq, _out, _to_video, _viewer = _prepare_output_path(
        format_=format_, force=force)

    # Apply flipbook settings
    _opts = _sv.flipbookSettings().stash()
    _opts.output(_seq.path.replace('%04d', '$F4'))
    _opts.frameRange(_rng)
    _opts.outputToMPlay(False)
    if _cam:
        _res = _cam.parmTuple('res').eval()
        _LOGGER.info(' - RES %s', _res)
        _opts.useResolution(True)
        _opts.resolution(_res)

    # Execute flipbook
    _seq.test_dir()
    _sv.flipbook(_vp, _opts)
    assert _seq.to_frames(force=True)
    _LOGGER.info(' - FLIPBOOK COMPLETE')

    # Post processing
    if _to_video:
        _LOGGER.info(' - MAKING MOV')
        _seq.to_video(_out, fps=_fps, burnins=burnins)
        _seq.delete(force=True)
    if view:
        _LOGGER.info(' - MPLAY %s', _mplay)
        _viewer.view(_out)
    _work.update_outputs()
