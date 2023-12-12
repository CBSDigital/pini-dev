"""Provides a universal interface for the host dcc.

This allows any host dcc to be operated using the same commands.
"""

import logging

from .dcc import DCC, DCCS

_LOGGER = logging.getLogger(__name__)

# Map functions to global level
for _name in dir(DCC):
    if _name.startswith('__'):
        continue
    _func = getattr(DCC, _name)
    globals()[_name] = _func
