"""Tools for managing PublishedFile entries in shotgrid."""

import logging
import operator
import time

from pini import pipe
from pini.tools import release
from pini.utils import abs_path, passes_filter, Seq

from . import sg_handler, sg_job, sg_task, sg_entity, sg_utils

_LOGGER = logging.getLogger(__name__)
_PUB_FILE_FIELDS = [
    'path', 'published_file_type', 'name', 'path_cache', 'id']


def create_pub_file(
        output, thumb=None, status='cmpt', update_cache=True, force=False):
    """Create PublishedFile entry in shotgrid.

    Args:
        output (CPOutput): output to register
        thumb (File): apply thumbnail image
        status (str): status for entry (default is complete)
        update_cache (bool): update cache on create
            (disable for multiple creates)
        force (bool): if an entry exists, update data

    Returns:
        (dict): registered data
    """
    from pini.pipe import shotgrid
    _LOGGER.info('CREATE PUB FILE %s', output)

    # Catch already exists
    _existing_id = to_pub_file_id(output)
    if _existing_id:
        _LOGGER.info(' - ALREADY REGISTERED IN SHOTGRID %d %s',
                     _existing_id, output.path)
        if not force:
            return to_pub_file_data(output)

    _LOGGER.debug(' - CREATE PUBLISHED FILE %s', output.path)
    _notes = output.metadata.get('notes')

    _sg_type = shotgrid.SGC.find_pub_type(
        output.extn, type_='Sequence' if isinstance(output, Seq) else 'File')
    _sg_ety = shotgrid.SGC.find_entity(output.entity)
    _sg_user = shotgrid.SGC.find_user()
    _sg_job = shotgrid.SGC.find_job(output.job)
    _sg_task = shotgrid.SGC.find_task(
        entity=output.entity, step=output.step, task=output.task)

    # Build data
    _data = {
        'code': output.filename,
        'created_by': _sg_user.to_entry(),
        'description': _notes,
        'entity': _sg_ety.to_entry(),
        'name': output.filename,
        'path_cache': pipe.JOBS_ROOT.rel_path(output.path),
        'project': _sg_job.to_entry(),
        'published_file_type': _sg_type.to_entry(),
        'task': _sg_task.to_entry(),
        'sg_status_list': status,
        'updated_by': _sg_user.to_entry(),
        'version_number': output.ver_n,
    }

    # Apply to shotgrid
    if not _existing_id:
        _result = sg_handler.create('PublishedFile', _data)
        _LOGGER.debug(' - RESULT %s', _result)
        _id = _result['id']
    else:
        for _field in ['created_by', 'updated_by']:
            _data.pop(_field)
        sg_handler.update('PublishedFile', _existing_id, _data)
        _id = _existing_id

    # Update cache
    if update_cache:
        _sg_job.find_pub_files(force=True, progress=True)
        assert _sg_job.find_pub_file(output)
        _job_c = pipe.CACHE.obt(output.job)
        _job_c.find_outputs(force=True)
        _out_c = pipe.CACHE.obt(output)
        assert _out_c

    # Apply thumb
    _thumb = thumb
    if not _thumb and isinstance(output, Seq):
        _thumb = output.to_frame_file()
    if _thumb:
        _LOGGER.debug(' - APPLY THUMB %s', _thumb)
        assert _thumb.exists()
        sg_handler.to_handler().upload_thumbnail(
            'PublishedFile', _id, _thumb.path)

    return _data


def _build_filters(
        job=None, entity=None, entities=None, work_dir=None, id_=None):
    """Build shotgrid pub files request filters.

    Args:
        job (CPJob): job to search
        entity (CPEntity): apply entity filter
        entities (CPEntity list): filter by the given list of entities
        work_dir (CPWorkDir): filter by work dir
        id_ (int): filter by pub file id

    Returns:
        (tuple list): filters
    """
    _LOGGER.debug(' - BUILDING FILTERS')

    _filters = [
        sg_job.to_job_filter(job),
        ('sg_status_list', 'not_in', ('omt', ))]

    if entity:
        _LOGGER.debug(' - BUILDING ENTITY FILTER')
        _filters += [sg_entity.to_entity_filter(entity)]
    if entities:
        _LOGGER.debug(' - BUILDING ENTITIES FILTER')
        _filters += [sg_entity.to_entities_filter(entities)]
    if work_dir:
        _LOGGER.debug(' - BUILDING WORK DIR FILTER')
        _filters += [sg_task.to_task_filter(work_dir)]
    if id_:
        _LOGGER.debug(' - BUILDING ID FILTER')
        _filters += [('id', 'is', id_)]

    return _filters


def _build_outputs(job, results, progress, use_cache=True):
    """Build output objects from the given list of shotgrid results.

    Args:
        job (CCPJob): parent job
        results (tuple list): list of paths and shotgrid results
        progress (bool): show progress on build object lists
        use_cache (bool): use cached output template mapping

    Returns:
        (CPOutput list): outputs
    """
    from pini import qt

    _cache = None
    _cache_updated = False
    if use_cache:
        _cache = job.get_sg_output_template_map()

    # Convert into output objects
    _o_start = time.time()
    _outs = []
    for _idx, (_path, _result) in qt.progress_bar(
            enumerate(results), 'Converting {:d} paths', show=progress,
            stack_id='BuildingShotgridOutputs'):

        _LOGGER.log(9, '[%d] PATH %s', _idx, _path)

        if _cache and _path in _cache:
            _pattern = _cache[_path]
            _LOGGER.log(9, ' - PATTERN %s', _pattern)
            if not _pattern:
                continue
            _tmpl = job.find_template_by_pattern(_pattern)
            _LOGGER.log(9, ' - TEMPLATE %s', _tmpl)
            _out = pipe.to_output(_path, job=job, template=_tmpl, catch=False)
            _LOGGER.log(9, ' - OUT %s', _out)

        else:
            _out = pipe.to_output(_path, job=job, catch=True)
            if use_cache:
                if not _out:
                    _pattern = None
                else:
                    _tmpl = _out.template
                    _LOGGER.log(9, ' - TEMPLATE %s', _tmpl)
                    _pattern = _tmpl.source.pattern
                    _LOGGER.log(9, ' - PATTERN %s', _pattern)
                _cache[_path] = _pattern
                _cache_updated = True

        _LOGGER.log(9, ' - OUT %s', _out)
        if not _out:
            _LOGGER.log(9, ' - REJECTED %s', _path)
            continue

        to_pub_file_data(_out, data=_result, force=True)  # Update cache
        _LOGGER.log(9, ' - ACCEPTED %s', _path)

        _outs.append(_out)

    if _cache_updated:
        job.get_sg_output_template_map(_cache, force=True)
        _LOGGER.info(' - UPDATED SG OUTPUT TMPL MAP')

    _LOGGER.debug(
        ' - BUILT %d OUTS (%.01fs)', len(_outs), time.time() - _o_start)

    return _outs


def find_pub_files(
        job=None, entity=None, entities=None, work_dir=None, id_=None,
        filter_=None, progress=False, use_cache=True):
    """Find PublishedFile entries.

    Args:
        job (CPJob): job to search
        entity (CPEntity): apply entity filter
        entities (CPEntity list): filter by the given list of entities
        work_dir (CPWorkDir): filter by work dir
        id_ (int): filter by pub file id
        filter_ (str): apply path filter
        progress (bool): show progress
        use_cache (bool): use cached output template mapping

    Returns:
        (CPOutput list): outputs
    """
    from pini import qt
    release.apply_deprecation('27/03/24', 'Use shotgrid.SGC')

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
    _job = pipe.CACHE.obt(_job)

    # Request data
    _filters = _build_filters(
        job=_job, entity=entity, entities=entities, work_dir=work_dir, id_=id_)
    _LOGGER.debug(' - FILTERS %s', _filters)
    _f_start = time.time()
    _results = sg_handler.find(
        'PublishedFile', fields=_PUB_FILE_FIELDS,
        filters=_filters)
    _LOGGER.debug(
        ' - FOUND %d RESULTS (%.01fs)', len(_results), time.time() - _f_start)

    # Find paths
    _p_start = time.time()
    _paths = {}
    for _idx, _result in qt.progress_bar(
            enumerate(_results), 'Checking {:d} results', show=progress,
            stack_id='CheckShotgridPaths'):
        _LOGGER.log(8, '[%d] ADDING RESULT %s', _idx, _result)
        _path = _result.get('path_cache')
        if not _path:
            _path_dict = _result.get('path') or {}
            _path = _path_dict.get('local_path')
        if not _path:
            continue
        _path = abs_path(_path, root=pipe.JOBS_ROOT)
        if not passes_filter(_path, filter_):
            continue
        if _path in _paths:
            continue
        _paths[_path] = _result
    _paths = sorted(_paths.items(), key=operator.itemgetter(0))
    _LOGGER.debug(
        ' - FOUND %d PATHS (%.01fs)', len(_paths), time.time() - _p_start)

    _outs = _build_outputs(
        job=_job, results=_paths, progress=progress, use_cache=use_cache)
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
    _LOGGER.log(9, ' - TO PUB FILE DATA %s', output)
    assert isinstance(output, pipe.CPOutputBase)
    _data = data
    _LOGGER.log(9, ' - DATA (A) %s', _data)
    if not _data:
        _LOGGER.debug(' - FIND PUB FILE DATA %s', output.path)
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
