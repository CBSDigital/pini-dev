"""Tools for managing the cacheable pipline root."""

# pylint: disable=wrong-import-position

from ... import MASTER

if MASTER == 'disk':
    from .ccp_root_disk import CCPRootDisk as CCPRoot
elif MASTER == 'shotgrid':
    from .ccp_root_sg import CCPRootSG as CCPRoot
else:
    raise ValueError(MASTER)
