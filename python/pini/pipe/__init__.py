"""Access point for pipeline module."""

# pylint: disable=invalid-name,wrong-import-position

import os

VERSION = 6

from ..pipe_5 import *

shotgrid = None
if MASTER == 'shotgrid':
    from ..pipe_5 import shotgrid
from ..pipe_5 import cp_template
