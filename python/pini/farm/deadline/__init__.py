"""Tools for manging deadline render farm."""

from .d_farm import CDFarm
from .d_job import CDPyJob
from .d_utils import setup_deadline_submit

FARM = CDFarm()
DEADLINE = FARM
NAME = FARM.NAME
