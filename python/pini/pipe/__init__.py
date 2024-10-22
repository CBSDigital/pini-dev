"""Access point for pipeline module."""

# pylint: disable=invalid-name,wrong-import-position

import os

shotgrid = None

# Select pipeline version
if os.environ.get('PINI_DEV') == '1':
    VERSION = 5
else:
    VERSION = 5

# Import corresponding version
if VERSION == 5:
    from ..pipe_5 import *
    if MASTER == 'shotgrid':
        from ..pipe_5 import shotgrid
    from ..pipe_5 import cp_template
elif VERSION == 4:
    from ..pipe_2 import *
    if MASTER == 'shotgrid':
        from ..pipe_2 import shotgrid
else:
    raise ValueError(VERSION)
