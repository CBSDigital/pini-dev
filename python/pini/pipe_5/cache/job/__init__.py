"""Tools for managing cacheable job objects."""

# pylint: disable=wrong-import-position

from ... import MASTER

if MASTER == 'disk':
    from .ccp_job_disk import CCPJobDisk as CCPJob
elif MASTER == 'shotgrid':
    from .ccp_job_sg import CCPJobSG as CCPJob
else:
    raise ValueError(MASTER)
