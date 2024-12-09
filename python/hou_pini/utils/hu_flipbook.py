"""General flipbooking utilities."""

import logging

import hou
import toolutils  # pylint: disable=import-error

from pini import dcc
from pini.utils import find_viewer, File, TMP

_LOGGER = logging.getLogger(__name__)


def flipbook(seq, view=True, range_=None, viewer=None, force=False):
    """Execute flipbook.

    Args:
        seq (Seq): output image sequence
        view (bool): view flipbook on completion
        range_ (tuple): override flipbook range start/end
        viewer (Viewer): override viewer
        force (bool): replace existing without confirmation
    """
    _LOGGER.info('FLIPBOOK')

    _viewer = viewer or find_viewer('mplay')
    _sv = toolutils.sceneViewer()
    _vp = _sv.curViewport()
    _cam = _vp.camera()
    _fps = dcc.get_fps()
    _LOGGER.info(' - CAM %s', _cam)

    # Determine range
    if range_:
        _rng = range_
    else:
        _rng = dcc.t_range()
    _LOGGER.info(' - RANGE %d-%d', *_rng)

    # Apply flipbook settings
    _opts = _sv.flipbookSettings().stash()
    _opts.output(seq.path.replace('%04d', '$F4'))
    _opts.frameRange(_rng)
    _opts.outputToMPlay(False)
    if _cam:
        _res = _cam.parmTuple('res').eval()
        _LOGGER.info(' - RES %s', _res)
        _opts.useResolution(True)
        _opts.resolution(_res)

    # Execute flipbook
    seq.test_dir()
    if not force and seq.exists():
        seq.delete(wording='replace')
    _sv.flipbook(_vp, _opts)
    assert seq.to_frames(force=True)
    _LOGGER.info(' - FLIPBOOK COMPLETE')

    if view:
        _viewer.view(seq)


def flipbook_frame(file_, force=False):
    """Flipbook a single frame.

    Args:
        file_ (File): output file
        force (bool): overwrite existing without confirmation

    Returns:
        (File): written file
    """
    _file = File(file_)
    _file.delete(force=force, wording='replace')
    _tmp_seq = TMP.to_seq('pini/tmp.%04d.jpg')
    _tmp_seq.delete(force=True)
    assert not _tmp_seq.frames
    _rng = [hou.frame(), hou.frame()]
    flipbook(_tmp_seq, range_=_rng, force=True, view=False)
    _LOGGER.info(' - TMP SEQ %s %s', _tmp_seq.frames, _tmp_seq)
    _tmp_seq.to_frame_file().move_to(_file)
    return _file
