"""Tools for managing job objects."""

# pylint: disable=wrong-import-position

from ... import MASTER

if MASTER == 'disk':
    from .cp_job_disk import CPJobDisk as CPJob
elif MASTER == 'shotgrid':
    from .cp_job_sg import CPJobSG as CPJob
else:
    raise ValueError(MASTER)

from .cp_job_tools import cur_job, to_job
