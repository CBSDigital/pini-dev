"""Tools for managing cacheable work dir objects."""

# pylint: disable=wrong-import-position

from ... import MASTER

if MASTER == 'disk':
    from .ccp_work_dir_disk import CCPWorkDirDisk as CCPWorkDir
elif MASTER == 'shotgrid':
    from .ccp_work_dir_sg import CCPWorkDirSG as CCPWorkDir
else:
    raise ValueError(MASTER)
