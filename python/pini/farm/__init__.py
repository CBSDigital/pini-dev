"""Tools for managing render farms."""

import logging
import os

from .base import CFarm

_LOGGER = logging.getLogger(__name__)
NAME = os.environ.get('PINI_FARM')
FARM = ICON = None
IS_AVAILABLE = False

if NAME == "Deadline":
    from .deadline import FARM, CDPyJob, setup_deadline_submit
    IS_AVAILABLE = True
elif NAME is None:
    pass
else:
    raise NotImplementedError(NAME)

# Map functions to global level
if FARM:
    for _name in dir(FARM):
        if _name.startswith('__'):
            continue
        _attr = getattr(FARM, _name)
        globals()[_name] = _attr
