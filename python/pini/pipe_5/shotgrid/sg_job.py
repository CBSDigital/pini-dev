"""Tools for managing shotgrid jobs (projects)."""

import logging
import os

from pini import qt, pipe
from pini.utils import norm_path

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
    if shotgrid.SGC.find_proj(_job, catch=True):
        raise RuntimeError('Job already exists on shotgrid ' + _job.name)

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
            f'Register job {_job.name} on shotgrid?\n\n{_job.path}',
            icon=shotgrid.ICON, title='Shotgrid')

    return [_sg.create('Project', _data)]
