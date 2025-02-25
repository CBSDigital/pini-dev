"""Tools for managing work directory objects."""

# pylint: disable=wrong-import-position

from ... import MASTER

if MASTER == 'disk':
    from .cp_work_dir_disk import CPWorkDirDisk as CPWorkDir
elif MASTER == 'shotgrid':
    from .cp_work_dir_sg import CPWorkDirSG as CPWorkDir
else:
    raise ValueError(MASTER)

from .cp_work_dir_tools import (
    cur_work_dir, to_work_dir, cur_task, map_task)
