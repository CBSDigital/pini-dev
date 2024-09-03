"""Module for managing which cacheable entity to use based on pipeline."""

# pylint: disable=unused-import

from ... import MASTER

if MASTER == 'disk':
    from .ccp_ety_disk import CCPEntityDisk as CCPEntity
elif MASTER == 'shotgrid':
    from .ccp_ety_sg import CCPEntitySG as CCPEntity
else:
    raise ValueError(MASTER)
