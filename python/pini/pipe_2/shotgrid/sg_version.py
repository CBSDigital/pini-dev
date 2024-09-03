"""Tools for manging shotgrid versions."""

import logging
import pprint

from pini import qt
from pini.utils import Seq, get_user, TMP, clip, File

from . import sg_handler, sg_entity, sg_utils

_LOGGER = logging.getLogger(__name__)


def create_version(
        video, frames, comment, thumb=None, filmstrip=None, pub_files=(),
        force=False):
    """Register the given video in shotgrid.

    Args:
        video (CPOutputVideo): output video to register
        frames (CPOutputSeq): source frames
        comment (str): submission comment
        thumb (File): override thumbnail
        filmstrip (File): override filmstrip
        pub_files (CPOutput list): published files to link
        force (bool): force re-register if already exists

    Returns:
        (SGVersion): version
    """
    from pini.pipe import shotgrid
    _LOGGER.info('CREATE VERSION')

    # Check for existing
    _cur_ver = shotgrid.SGC.find_ver(video, catch=True)
    if not force and _cur_ver:
        _LOGGER.info(' - VERSION ALREADY EXISTS %s', video)
        return _cur_ver

    # Create version
    _data = _build_ver_data(
        video, frames=frames, comment=comment, pub_files=pub_files)
    _LOGGER.debug('DATA %s', pprint.pformat(_data))
    if not _cur_ver:
        shotgrid.create('Version', _data)
        _action = 'CREATED'
    else:
        _data.pop('created_by')
        shotgrid.update('Version', _cur_ver.id_, _data)
        _action = 'UPDATED'
    _sg_ver = shotgrid.SGC.find_ver(video, force=1)
    _LOGGER.info(' - %s VERSION %s', _action, _sg_ver)
    assert _sg_ver

    # Upload movie
    shotgrid.upload('Version', _sg_ver.id_, video)

    # Apply thumb
    if thumb:
        _thumb = File(thumb)
        _LOGGER.debug(' - APPLY THUMB %s', _thumb)
        assert _thumb.exists()
        shotgrid.upload_thumbnail('Version', _sg_ver.id_, _thumb.path)

    # Apply filmstrip
    if filmstrip:
        _strip = File(filmstrip)
        shotgrid.upload_filmstrip_thumbnail(
            'Version', _sg_ver.id_, _strip.path)

    return _sg_ver


def _build_ver_data(video, frames, comment, pub_files):
    """Build version data dict.

    Args:
        video (CPOutputVideo): output video to register
        frames (CPOutputSeq): source frames
        comment (str): submission comment
        pub_files (CPOutput list): published files to link

    Returns:
        (dict): version data
    """
    from pini.pipe import shotgrid

    _work = sg_utils.output_to_work(video)
    _sg_ety = shotgrid.SGC.find_entity(video.entity)
    _sg_job = shotgrid.SGC.find_job(video.job)
    _sg_task = shotgrid.SGC.find_task(video)

    # Build data
    _data = {
        "code": video.base,
        "entity": _sg_ety.to_entry(),
        "project": _sg_job.to_entry(),
        "sg_task": _sg_task.to_entry(),
        "sg_path_to_movie": video.path,
    }
    if 'sg_pini_tag' in shotgrid.find_fields('Version'):
        _data["sg_pini_tag"] = video.tag or ''

    # Add frames data
    if frames:
        assert isinstance(frames, Seq)
        _start, _end = frames.to_range(force=True)
        _data['sg_path_to_frames'] = frames.path
        _data['sg_first_frame'] = _start
        _data['sg_last_frame'] = _end

    # Add user data
    _user = video.metadata.get('owner') or get_user()
    if _user:
        _sg_user = shotgrid.SGC.find_user(_user)
        _data['user'] = _sg_user.to_entry()
        _data['created_by'] = _sg_user.to_entry()

    # Add description
    _desc = comment
    if not _desc and _work:
        _desc = _work.notes
    if _desc:
        _data['description'] = _desc

    # Add published files
    if pub_files:
        _outs = sorted(set(pub_files) | {video})
        _LOGGER.info(' - OUTS %s', _outs)
        _data['published_files'] = []
        for _out in _outs:
            _sg_pub_file = shotgrid.SGC.find_pub_file(_out)
            _data['published_files'].append(_sg_pub_file.to_entry())

    return _data


def _build_filmstrip(video):
    """Build filmstrip image from the given video.

    NOTE: shotgrid does this automatically when a video is applied
    to the sg_uploaded_movie field of a version entry, so this
    function isn't needed.

    Args:
        video (Video): video to convert

    Returns:
        (File): filmstrip file
    """
    _strip = TMP.to_file('PiniTmp/strip.jpg')

    _LOGGER.debug(' - DUR %f', video.to_dur())
    _LOGGER.debug(' - FPS %f', video.to_fps())
    _res = video.to_res()
    _strip_height = int(240.0*_res[1]/_res[0])
    _LOGGER.debug(' - RES %s', _res)
    _n_frames = int(video.to_dur() * video.to_fps())
    _max_frames = int(32000 / 240)
    _LOGGER.debug(' - N FRAMES %d (MAX %d)', _n_frames, _max_frames)
    if _n_frames < _max_frames:
        _strip_fps = None
    else:
        _strip_fps = int(_max_frames / video.to_dur())
    _LOGGER.debug(' - STRIP FPS %s', _strip_fps)

    # Render out tmp seq
    _tmp_seq_res = 240, _strip_height
    _LOGGER.debug(' - TMP SEQ RES (A) %s', _tmp_seq_res)
    _tmp_seq = TMP.to_seq('PiniTmp/imgs.%04d.jpg')
    _tmp_seq.delete(force=True)
    video.to_seq(_tmp_seq, res=_tmp_seq_res, fps=_strip_fps, verbose=1)
    _LOGGER.debug(' - TMP SEQ %s', _tmp_seq)
    assert _tmp_seq.frames
    _LOGGER.debug(' - TMP SEQ RES (B) %s', _tmp_seq.to_res())
    assert _tmp_seq.to_res() == _tmp_seq_res
    _n_frames = len(_tmp_seq.frames)

    # Render tmp seq to video
    _tmp_seq_res = (240, int(_strip_height/2)*2)
    _tmp_vid = TMP.to_file('PiniTmp/video.mp4', class_=clip.Video)
    _tmp_seq.to_video(_tmp_vid, res=_tmp_seq_res, force=True)

    # Build filmstrip
    _strip_width = 240*_n_frames
    assert _strip_width < 32767
    _pix = qt.CPixmap(_strip_width, _strip_height)
    _LOGGER.info(' - TMP SEQ %s %s', _tmp_seq.frames, _tmp_seq)
    for _idx, _frame in enumerate(_tmp_seq.frames):
        _file = _tmp_seq[_frame]
        # _LOGGER.info(_file)
        _pos = (240*_idx, 0)
        _pix.draw_overlay(_file, pos=_pos)
    _pix.save_as(_strip, force=True)

    return _strip


def to_version_data(output, fields=None):
    """Obtain version data for the given output.

    Args:
        output (CPOutputBase): output video/seq to find data for
        fields (str list): override fields to request

    Returns:
        (dict): shotgrid data
    """
    _filters = [
        sg_entity.to_entity_filter(output),
        ('code', 'is', output.base),
        ('sg_status_list', 'not_in', ('na', 'omt')),
    ]
    _fields = fields or [
        'sg_path_to_frames',
        'sg_path_to_movie',
        'sg_uploaded_movie',
        'user',
    ]
    return sg_handler.find_one('Version', filters=_filters, fields=_fields)


def to_version_id(output):
    """Obtain version id for the given output.

    Args:
        output (CPOutputBase): output video/seq to find id for

    Returns:
        (int|None): version id (if any)
    """
    _data = to_version_data(output)
    if not _data:
        return None
    return _data['id']
