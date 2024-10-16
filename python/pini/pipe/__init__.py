"""Access point for pipeline module."""

# pylint: disable=invalid-name,wrong-import-position

import os

shotgrid = None

if os.environ.get('PINI_DEV') == '1':
    VERSION = 4
    # VERSION = 5
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
else:
    from ..pipe_2 import *
    if MASTER == 'shotgrid':
        from ..pipe_2 import shotgrid
    VERSION = 4
