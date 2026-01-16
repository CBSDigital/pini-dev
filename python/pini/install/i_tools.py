"""Module for setting up tool instances."""

import os


def read_env(var, default=False):
    """Read a pini environment variable.

    Args:
        var (str): name of env var
        default (bool): default value (applied if env not found)

    Returns:
        (bool): value of env var
    """
    _val = os.environ.get(var, default)
    if _val in ('', '0', 'False', False):
        return False
    if _val in ('1', 'True', True):
        return True
    raise NotImplementedError(f'Unhandled value ${var} as {_val}')
