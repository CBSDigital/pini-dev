"""Tools for managing session data."""

import hashlib
import sys
import time

PINI_SESSION_ID = hashlib.md5(f"{time.time()}".encode('utf-8')).hexdigest()[:10]
PINI_SESSION_START = time.time()

# Set up dcc session id/start
if not hasattr(sys, 'DCC_SESSION_ID'):
    DCC_SESSION_ID = PINI_SESSION_ID
    sys.DCC_SESSION_ID = PINI_SESSION_ID
else:
    DCC_SESSION_ID = sys.DCC_SESSION_ID
if not hasattr(sys, 'DCC_SESSION_START'):
    DCC_SESSION_START = PINI_SESSION_START
    sys.DCC_SESSION_START = PINI_SESSION_START
else:
    DCC_SESSION_START = sys.DCC_SESSION_START


def to_session_dur(mode='dcc'):
    """Obtain session duration.

    Args:
        mode (str): duration to obtain
            dcc - time since dcc launch
            pini - time since pini import/reload

    Returns:
        (float): session duration (in seconds)
    """
    if mode == 'dcc':
        _start = DCC_SESSION_START
    elif mode == 'pini':
        _start = PINI_SESSION_START
    else:
        raise ValueError
    return time.time() - _start
