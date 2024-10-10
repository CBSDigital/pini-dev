"""Module to build the CPEntity object based on the current pipeline."""

# pylint: disable=unused-import

from ... import MASTER

if MASTER == 'disk':
    from .cp_ety_disk import CPEntityDisk as CPEntity
elif MASTER == 'shotgrid':
    from .cp_ety_sg import CPEntitySG as CPEntity
else:
    raise ValueError(MASTER)
