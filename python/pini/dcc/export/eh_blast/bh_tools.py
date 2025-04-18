"""Tools for managing function access to blast."""

import logging

from pini import dcc
from pini.utils import single

_LOGGER = logging.getLogger(__name__)


def blast(**kwargs):
    """Blast current scene.

    Returns:
        (CPOutput): blast
    """
    _exp = dcc.find_export_handler('Playblast Flipbook')
    _exp.exec(**kwargs)
    return single(_exp.outputs)
