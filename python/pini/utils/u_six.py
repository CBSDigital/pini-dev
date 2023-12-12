"""Tools for managing python 3 compliance."""

# pylint: disable=ungrouped-imports,no-name-in-module,unused-import,deprecated-class,deprecated-module,undefined-variable

import sys

if sys.version_info.major == 3:
    from collections.abc import Iterable as SixIterable
    from enum import IntEnum as SixIntEnum
    from importlib import reload as six_reload
    from sys import maxsize as six_maxint
elif sys.version_info.major == 2:
    from collections import Iterable as SixIterable
    from enum import Enum as SixIntEnum
    from imp import reload as six_reload
    from sys import maxint as six_maxint
else:
    raise ImportError


def six_cmp(obj_a, obj_b):
    """Replaces py2 cmp builtin.

    Args:
        obj_a (any): first object
        obj_b (any): second object

    Returns:
        (int): cmp result
    """
    return (obj_a > obj_b) - (obj_a < obj_b)


def six_execfile(file_):
    """Execute code in a file (list execfile in py2) that works in py3.

    NOTE: this has some weird behaviour with globals that could be
    ironed out.

    Args:
        file_ (str): file to execute
    """
    from pini.utils import to_str
    _file = to_str(file_)
    with open(_file) as _handle:
        _code = compile(_handle.read(), _file, 'exec')
        exec(_code)  # pylint: disable=exec-used


def six_long(val):
    """Convert to long in py2, otherwise do nothing.

    Args:
        val (int): value to convert

    Returns:
        (long): long value
    """
    if sys.version_info.major == 3:
        return int(val)
    return long(val)
