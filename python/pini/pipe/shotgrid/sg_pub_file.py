"""Tools for managing PublishedFile entries in shotgrid."""

import logging
import operator
import time

from pini import pipe
from pini.utils import abs_path, passes_filter, Seq

from . import sg_handler, sg_job, sg_task, sg_user, sg_entity, sg_utils

_LOGGER = logging.getLogger(__name__)
_PUB_FILE_FIELDS = [
    'path', 'published_file_type', 'name', 'path_cache', 'id']


def create_pub_file(output, thumb=None, force=False):
    """Create PublishedFile entry in shotgrid.

    Args:
        output (CPOutput): output to register
        thumb (File): apply thumbnail image
        force (bool): if an entry exists, update data

    Returns:
        (dict): registered data
    """
    _LOGGER.info('CREATE PUB FILE %s', output)

    # Catch already exists
    _existing_id = to_pub_file_id(output)
    if _existing_id:
        _LOGGER.info(' - ALREADY REGISTERED IN SHOTGRID %d %s',
                     _existing_id, output.path)
        if not force:
            return to_pub_file_data(output)

    _LOGGER.info('CREATE PUBLISHED FILE %s', output.path)
    _notes = output.metadata.get('notes')

    # Find type
    _code = {
        'ma': 'Maya Scene',
        'abc': 'Abc File',
        'mp4': 'Movie',
    }.get(output.extn, output.extn)
    _type = sg_handler.find_one(
        'PublishedFileType', filters=[('code', 'is', _code)])

    # Build data
    _data = {
        'code': output.filename,
        'created_by': sg_user.to_user_data(),
        'description': _notes,
        'entity': sg_entity.to_entity_data(output),
        'name': output.filename,
        'path_cache': pipe.JOBS_ROOT.rel_path(output.path),
        'project': sg_job.to_job_data(output.job),
        'published_file_type': _type,
        'task': sg_task.to_task_data(output),
        'sg_status_list': 'cmpt',
        'updated_by': sg_user.to_user_data(),
        'version_number': output.ver_n,
    }
    if not _existing_id:
        _result = sg_handler.create('PublishedFile', _data)
        _LOGGER.info(' - RESULT %s', _result)
        _id = _result['id']
        to_pub_file_data(output, data=_result, force=True)  # Update cache
    else:
        for _field in ['created_by', 'updated_by']:
            _data.pop(_field)
        sg_handler.update('PublishedFile', _existing_id, _data)
        _id = _existing_id

    # Apply thumb
    _thumb = thumb
    if not _thumb and isinstance(output, Seq):
        _thumb = output.to_frame_file()
    if _thumb:
        _LOGGER.info(' - APPLY THUMB %s', _thumb)
        assert _thumb.exists()
        sg_handler.to_handler().upload_thumbnail(
            'PublishedFile', _id, _thumb.path)

    return _data


def find_pub_files(job=None, entity=None, work_dir=None, filter_=None):
    """Find PublishedFile entries.

    Args:
        job (CPJob): job to search
        entity (CPEntity): apply entity filter
        work_dir (CPWorkDir): filter by work dir
        filter_ (str): apply path filter

    Returns:
        (CPOutput list): outputs
    """
    _start = time.time()
    _LOGGER.debug('FIND PUB FILES')

    # Determine job
    _job = job
    if not _job and work_dir:
        _job = work_dir.job
    if not _job and entity:
        _job = entity.job
    if not _job:
        _job = pipe.cur_job()

    # Request data
    _filters = [
        sg_job.to_job_filter(_job),
        ('sg_status_list', 'not_in', ('omt', ))]
    if entity:
        _filters += [sg_entity.to_entity_filter(entity)]
    if work_dir:
        _filters += [sg_task.to_task_filter(work_dir)]
    _LOGGER.debug(' - FILTERS %s', _filters)
    _results = sg_handler.find(
        'PublishedFile', fields=_PUB_FILE_FIELDS,
        filters=_filters)
    _LOGGER.debug(' - FOUND %d RESULTS', len(_results))

    # Find paths
    _paths = []
    for _result in _results:
        _path = _result['path_cache']
        if not _path:
            continue
        _path = abs_path(_path, root=pipe.JOBS_ROOT)
        if not passes_filter(_path, filter_):
            continue
        _paths.append((_path, _result))
    _paths.sort(key=operator.itemgetter(0))
    _LOGGER.debug(' - FOUND %d PATHS', len(_paths))

    # Convert into output objects
    _outs = []
    for _path, _result in _paths:
        _LOGGER.debug('PATH %s', _path)
        _out = pipe.to_output(_path, job=_job, catch=True)
        _LOGGER.debug(' - OUT %s', _out)
        if not _out:
            _LOGGER.debug(' - REJECTED %s', _path)
            continue
        to_pub_file_data(_out, data=_result, force=True)  # Update cache
        _LOGGER.debug(' - ACCEPTED %s', _path)
        _outs.append(_out)
    _outs.sort()
    _LOGGER.debug(
        ' - FOUND %d OUTS IN %.01fs', len(_outs), time.time() - _start)

    return _outs


@sg_utils.get_sg_result_cacher(use_args=['output'])
def to_pub_file_data(output, data=None, force=False):
    """Obtain shotgrid PublishedFile data for the given output.

    Args:
        output (CPOutput): output to find
        data (dict): force data into cache
        force (bool): force recache

    Returns:
        (dict): data
    """
    _LOGGER.debug(' - TO PUB FILE DATA %s', output)
    assert isinstance(output, pipe.CPOutputBase)
    _data = data
    _LOGGER.debug(' - DATA (A) %s', _data)
    if not _data:
        _LOGGER.info(' - FIND PUB FILE DATA %s', output.path)
        _data = sg_handler.find_one(
            'PublishedFile',
            fields=_PUB_FILE_FIELDS,
            filters=[
                ('name', 'is', output.filename),
                sg_job.to_job_filter(output.job)])
        _LOGGER.debug(' - DATA (B) %s', _data)
    assert isinstance(_data, dict) or _data is None
    return _data


def to_pub_file_id(output):
    """Obtain shotgrid PublishedFile id for the given output.

    Args:
        output (CPOutput): output to find

    Returns:
        (int): id
    """
    _data = to_pub_file_data(output)
    return _data['id'] if _data else None
