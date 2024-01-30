"""Tools for manging deadline render farm."""

from .d_farm import CDFarm
from .d_job import CDPyJob

FARM = CDFarm()
DEADLINE = FARM
NAME = FARM.NAME
