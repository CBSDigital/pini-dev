"""Tools for manging deadline render farm."""

from pini import dcc

from .d_farm import CDFarm
from .submit import (
    CDPyJob, CDCmdlineJob, CDJob, setup_deadline_submit, flush_old_submissions,
    write_deadline_data)

if dcc.NAME == 'maya':
    from .submit import CDMayaPyJob

FARM = CDFarm()
DEADLINE = FARM
NAME = FARM.NAME

for _name in ['submit_job']:
    _func = getattr(DEADLINE, _name)
    globals()[_name] = _func
