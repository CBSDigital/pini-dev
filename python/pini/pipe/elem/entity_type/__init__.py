"""Tools for manging entity type (eg. sequence, asset type) objects."""

# pylint: disable=wrong-import-position

from ... import MASTER

if MASTER == 'disk':
    from .cp_sequence_disk import CPSequenceDisk as CPSequence
elif MASTER == 'shotgrid':
    from .cp_sequence_sg import CPSequenceSG as CPSequence
else:
    raise ValueError(MASTER)

from .cp_sequence_tools import cur_sequence
