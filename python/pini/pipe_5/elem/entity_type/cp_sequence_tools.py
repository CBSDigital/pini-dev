"""General tools for managing shot sequences."""

import logging

_LOGGER = logging.getLogger(__name__)


def cur_sequence():
    """Obtain current sequence.

    Returns:
        (CPSequence|None): sequence (if any)
    """
    from pini import dcc, pipe
    _path = dcc.cur_file()
    if not _path:
        return None
    try:
        return pipe.CPSequence(_path)
    except ValueError:
        return None
