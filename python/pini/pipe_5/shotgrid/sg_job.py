"""Tools for managing shotgrid jobs (projects)."""

import logging
import os

from pini import qt, pipe
from pini.tools import release
from pini.utils import single, norm_path

from . import sg_handler, sg_utils

_LOGGER = logging.getLogger(__name__)

_JOB_TEMPLATE = os.environ.get(
    'PINI_SG_JOB_TEMPLATE', 'Film VFX Template')
_JOB_NAME_TOKEN = os.environ.get(
    'PINI_SG_JOB_NAME_TOKEN', 'name')
_JOB_FIELDS = [_JOB_NAME_TOKEN, 'sg_short_name', 'sg_frame_rate']


def create_job(job, force=False):
    """Register a job on shotgrid.

    Args:
        job (CPJob): job to create
        force (bool): create job without confirmation

    Returns:
        (list): job shotgrid data
    """
    from pini.pipe import shotgrid

    _LOGGER.debug('CREATE JOB %s', job)
    _sg = shotgrid.to_handler()

    # Determine job name
    if isinstance(job, pipe.CPJob):
        _job = job
    elif isinstance(job, str):
        assert '/' not in norm_path(job)
        _job = pipe.to_job(job)
    else:
        raise ValueError(job)
    _LOGGER.debug(' - JOB %s', _job)
    if to_job_data(_job, create=False, force=True):
        raise RuntimeError('Job already exists on shotgrid '+_job.name)

    # Find layout project (template)
    _lyt = _sg.find_one(
        'Project',
        [(_JOB_NAME_TOKEN, 'is', _JOB_TEMPLATE)],
        [_JOB_NAME_TOKEN])
    _LOGGER.debug(' - LAYOUT %s', _lyt)
    if not _lyt:
        raise RuntimeError('Unable to find shotgrid template job')

    # Build creation data
    _data = {
        'name': _job.name,
        'layout_project': _lyt}
    _LOGGER.debug(' - DATA %s', _data)
    if not force:
        qt.ok_cancel(
            'Register job {} on shotgrid?\n\n{}'.format(
                _job.name, _job.path),
            icon=shotgrid.ICON, title='Shotgrid')

    return [_sg.create('Project', _data)]


def find_job(match):
    """Find a single job by matching shotgrid data.

    Args:
        match (any): shotgrid data to match (eg. id)

    Returns:
        (CPJob): matching job
    """
    _jobs = find_jobs()

    _id_match = single(
        [_job for _job in _jobs if _job_to_data(_job)['id'] == match],
        catch=True)
    if _id_match:
        return _id_match

    raise ValueError(match)


def find_jobs():
    """Find jobs.

    Returns:
        (CPJob list): job
    """
    release.apply_deprecation('28/03/24', 'Use SGC')

    _LOGGER.debug('FIND JOBS')
    _results = sg_handler.find(
        'Project', fields=_JOB_FIELDS,
        filters=[('sg_status', 'in', ('Active', 'Bidding', 'Test'))])

    _disk_jobs = pipe.ROOT.find(type_='d', depth=1, full_path=False)
    _jobs = []
    for _data in _results:
        _name = _data[_JOB_NAME_TOKEN]
        if not _name:
            continue
        if _name not in _disk_jobs:
            continue
        _job = pipe.to_job(_name)
        _job_to_data(_job, data=[_data], force=True)  # Update cache
        _jobs.append(_job)

    return sorted(_jobs)


@sg_utils.get_sg_result_cacher(use_args=['job'])
def _job_to_data(job, data=None, create=True, force=False):
    """Obtain shotgrid data for the given job.

    Args:
        job (CPJob): job to read
        data (dict): force shotgrid data into cache
        create (bool): create job if missing
        force (bool): rewrite cache

    Returns:
        (dict): shotgrid data
    """
    assert isinstance(job, pipe.CPJob)
    _results = data or sg_handler.find(
        'Project',
        filters=[(_JOB_NAME_TOKEN, 'is', job.name)],
        fields=_JOB_FIELDS)
    assert len(_results) in (0, 1)

    # Create job if needed
    if not _results and pipe.MASTER == 'disk':
        if not create:
            return None
        _results = create_job(job)

    return single(_results)


def to_job_data(job=None, create=True, force=False):
    """To obtain shotgrid data for the given job.

    Args:
        job (str): path to job
        create (bool): create job if missing
        force (bool): force reread data from shotgrid

    Returns:
        (dict): shotgrid job data
    """
    _job = job
    if isinstance(_job, str):
        _job = pipe.CPJob(_job)
    if not _job:
        _job = pipe.cur_job()
    _LOGGER.debug('TO JOB DATA %s', _job)
    _LOGGER.debug(' - JOB NAME TOKEN %s', _JOB_NAME_TOKEN)

    # Search shotgrid
    return _job_to_data(_job, create=create, force=force)


def to_job_id(job):
    """Obtain job id for the given job.

    Args:
        job (CPJob): job to read

    Returns:
        (int): job id
    """
    return to_job_data(job)['id']


def to_job_filter(job=None):
    """Obtain job filter for the given job.

    Args:
        job (str): path to job

    Returns:
        (tuple): job (project) filter
    """
    _job = pipe.CPJob(job) if job else pipe.cur_job()
    return 'project', 'is', [to_job_data(_job)]
