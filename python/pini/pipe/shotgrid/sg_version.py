"""Tools for manging shotgrid versions."""

import logging
import pprint

from pini.utils import Seq, get_user

from . import sg_handler, sg_entity, sg_utils, sg_job, sg_task, sg_user

_LOGGER = logging.getLogger(__name__)


def create_version(video, frames, comment):
    """Register the given video in shotgrid.

    Args:
        video (CPOutputVideo): output video to register
        frames (CPOutputSeq): source frames
        comment (str): submission comment

    Returns:
        (dict): version data
    """
    _LOGGER.info('NEED TO CREATE VERSION')

    _work = sg_utils.output_to_work(video)

    _data = {
        "code": video.base,
        "sg_pini_tag": video.tag or '',
        "entity": sg_entity.to_entity_data(video.entity),
        "project": sg_job.to_job_data(video.job),
        "sg_task": sg_task.to_task_data(video),
        "sg_path_to_movie": video.path,
    }

    # Add frames data
    if frames:
        assert isinstance(frames, Seq)
        _start, _end = frames.to_range(force=True)
        _data['sg_path_to_frames'] = frames.path.replace('.%04d.', '.####.')
        _data['sg_first_frame'] = _start
        _data['sg_last_frame'] = _end

    # Add user data
    _user = video.metadata.get('owner') or get_user()
    if _user:
        _user_data = sg_user.to_user_data(_user)
        _data['user'] = _user_data
        _data['created_by'] = _user_data

    # Add description
    _desc = comment
    if not _desc and _work:
        _desc = _work.notes
    if _desc:
        _data['description'] = _desc

    # Create version
    _LOGGER.debug('DATA %s', pprint.pformat(_data))
    sg_handler.create('Version', _data)
    _LOGGER.info('CREATED VERSION')

    return to_version_data(video)


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
