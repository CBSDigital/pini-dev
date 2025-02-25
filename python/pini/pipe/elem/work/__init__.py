"""Tools for managing work file objects."""

# pylint: disable=wrong-import-position

from ... import MASTER

if MASTER == 'disk':
    from .cp_work_disk import CPWorkDisk as CPWork
elif MASTER == 'shotgrid':
    from .cp_work_sg import CPWorkSG as CPWork
else:
    raise ValueError(MASTER)

from .cp_work_tools import (
    cur_work, add_recent_work, install_set_work_callback,
    recent_work, load_recent, to_work, RECENT_WORK_YAML)

SET_WORK_CALLBACKS = {}
