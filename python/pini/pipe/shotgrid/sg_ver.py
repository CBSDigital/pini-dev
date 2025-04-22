"""Tools for manging shotgrid versions."""

import logging
import pprint

from pini.utils import Seq, get_user, File, TMP, Video, Image

from . import sg_utils

_LOGGER = logging.getLogger(__name__)


def create_ver(
        render, frames, comment, thumb=None, filmstrip=None, pub_files=(),
        force=False):
    """Register the given video in shotgrid.

    Args:
        render (CPOutputVideo|CPOutputSeq): output to register
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
    _ety = shotgrid.SGC.find_entity(render.entity)
    _cur_ver = _ety.find_ver(render, catch=True)
    if not force and _cur_ver:
        _LOGGER.info(' - VERSION ALREADY EXISTS %s', render)
        return _cur_ver

    # Create version
    _data = _build_ver_data(
        render, frames=frames, comment=comment, pub_files=pub_files)
    _LOGGER.debug('DATA %s', pprint.pformat(_data))
    if not _cur_ver:
        shotgrid.create('Version', _data)
        _action = 'CREATED'
    else:
        _data.pop('created_by')
        shotgrid.update('Version', _cur_ver.id_, _data)
        _action = 'UPDATED'
    _sg_ver = _ety.find_ver(render, force=True)
    _LOGGER.info(' - %s VERSION %s', _action, _sg_ver)
    assert _sg_ver

    # Upload video
    _video = None
    if isinstance(render, Video):
        _video = render
    if _video:
        shotgrid.upload(
            'Version', _sg_ver.id_, _video, field_name='sg_uploaded_movie')

    # Apply thumb
    _thumb = None
    if thumb:
        _thumb = File(_thumb)
    if isinstance(render, Seq):
        _thumb = render.to_frame_file()
    if not _thumb and _video:
        _thumb = TMP.to_file('tmp.jpg')
        render.to_frame(_thumb, force=True)
    if _thumb and _thumb.extn == 'exr':
        _tmp = TMP.to_file('tmp.jpg')
        Image(_thumb).convert(_tmp, force=True)
        _thumb = _tmp
    if _thumb:
        assert _thumb.exists()
        _LOGGER.info(' - APPLY THUMB %s', _thumb)
        shotgrid.upload_thumbnail('Version', _sg_ver.id_, _thumb.path)

    # Apply filmstrip (generated automatically if thumb)
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
    _sg_job = shotgrid.SGC.find_proj(video.job)
    _sg_task = _sg_ety.find_task(task=video.task, step=video.step)

    # Build data
    _data = {
        "code": video.base,
        "entity": _sg_ety.to_entry(),
        "project": _sg_job.to_entry(),
        "sg_task": _sg_task.to_entry(),
        "sg_path_to_movie": video.path,
        "sg_version_number": video.ver_n,
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
