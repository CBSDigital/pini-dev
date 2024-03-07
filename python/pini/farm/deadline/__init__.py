"""Tools for manging deadline render farm."""

from pini import dcc

from .d_farm import CDFarm
from .d_job import CDPyJob
from .d_utils import setup_deadline_submit, flush_old_submissions

if dcc.NAME == 'maya':
    from .d_maya_job import CDMayaPyJob

FARM = CDFarm()
DEADLINE = FARM
NAME = FARM.NAME
