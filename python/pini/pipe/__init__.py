"""Access point for pipeline module."""

# pylint: disable=invalid-name,wrong-import-position

import os

shotgrid = None

if os.environ.get('PINI_DEV') == '1':
    from ..pipe_2 import *
    if MASTER == 'shotgrid':
        from ..pipe_2 import shotgrid
    from ..pipe_2 import cp_template
else:
    from ..pipe_2 import *
    if MASTER == 'shotgrid':
        from ..pipe_2 import shotgrid

VERSION = 4
