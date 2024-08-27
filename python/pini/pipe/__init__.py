"""Access point for pipeline module."""

# pylint: disable=invalid-name,wrong-import-position

# For linter
shotgrid = None

from ..pipe_1 import *

if MASTER == 'shotgrid':
    from ..pipe_1 import shotgrid
