"""Tools for managing code deprecation."""

import time


def apply_deprecation(date, msg):
    """Apply a deprecation at this point in the code.

    This will raise a deprecation error if we are in dev mode,
    otherwise do nothing.

    Args:
        date (str): deprecation date string (used to remove code
            after a certain period on release)
        msg (str): deprecation message
    """
    from pini import testing
    if not testing.dev_mode():
        return
    _mtime = time.strptime(date, '%d/%m/%y')  # Check date is valid
    raise DeprecationWarning('{} ({})'.format(msg, date))
