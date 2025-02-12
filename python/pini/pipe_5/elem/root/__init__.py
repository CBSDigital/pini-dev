"""Tools for managing pipeline roots."""

# pylint: disable=wrong-import-position

import os

from pini.utils import HOME_PATH

from ... import MASTER

if MASTER == 'disk':
    from .cp_root_disk import CPRootDisk as CPRoot
elif MASTER == 'shotgrid':
    from .cp_root_sg import CPRootSG as CPRoot
else:
    raise ValueError(MASTER)

ROOT = CPRoot(os.environ.get(
    'PINI_JOBS_ROOT', HOME_PATH + '/Documents/Projects'))

# Map functions to global level
for _name in ['find_jobs', 'find_job', 'obt_job']:
    _func = getattr(ROOT, _name)
    globals()[_name] = _func
