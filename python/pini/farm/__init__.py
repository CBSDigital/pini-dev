"""Tools for managing render farms."""

import logging
import os

from .base import CFarm, set_farm

_LOGGER = logging.getLogger(__name__)
_PINI_FARM = os.environ.get('PINI_FARM')
NAME = FARM = IS_AVAILABLE = ICON = None

if _PINI_FARM == "Deadline":
    from .deadline import FARM, CDPyJob
elif _PINI_FARM is None:
    pass
else:
    raise NotImplementedError(_PINI_FARM)

# Map functions to global level
if FARM:
    set_farm(FARM)
