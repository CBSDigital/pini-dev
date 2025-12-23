"""General utilities relating to time."""

import datetime
import logging
import sys
import time

_LOGGER = logging.getLogger(__name__)

HOUR_SECS = 60 * 60
DAY_SECS = HOUR_SECS * 24
WEEK_SECS = DAY_SECS * 7
YEAR_SECS = DAY_SECS * 365.25


def nice_age(age, depth=2, pad=None, weeks=True, seconds=True):
    """Convert an age in seconds to a readable form (eg. 6w3d).

    Args:
        age (float): age in seconds
        depth (int): how many levels of detail to show
        pad (int): number padding
        weeks (bool): use weeks (otherwise skip to days)
        seconds (bool): include seconds

    Returns:
        (str): readable age
    """
    _LOGGER.debug('NICE AGE %s', age)
    _secs = round(age)
    _fmt = '{:d}' if not pad else f'{{:0{pad:d}d}}'
    _vals = []

    # Add weeks
    if weeks and _secs > 7 * 24 * 60 * 60:
        _wks = int(_secs / (7 * 24 * 60 * 60))
        _secs = _secs - _wks * 7 * 24 * 60 * 60
        _str = (_fmt + 'w').format(_wks)
        _vals.append(_str)

    # Add days
    if _secs > 24 * 60 * 60:
        _days = int(_secs / (24 * 60 * 60))
        _secs = _secs - _days * 24 * 60 * 60
        _str = (_fmt + 'd').format(_days)
        _vals.append(_str)

    # Add hours
    if _vals or _secs > 60 * 60:
        _hours = int(_secs / (60 * 60))
        _secs = _secs - _hours * 60 * 60
        _str = (_fmt + 'h').format(_hours)
        _vals.append(_str)

    # Add mins
    _LOGGER.debug(' - ADDING MINS %d', _secs)
    if (
            (_vals and _secs) or  # secs left but no minutes
            _secs > 60):
        _tail = len(_vals) + 1 >= depth
        _mins_f = _secs / 60
        _mins = round(_mins_f) if _tail else int(_mins_f)
        _str = (_fmt + 'm').format(_mins)
        _secs = _secs - _mins * 60
        _vals.append(_str)

    # Add secs
    _LOGGER.debug(' - ADDING SECONDS %d', _secs)
    if seconds and _secs:
        _str = (_fmt + 's').format(_secs)
        _vals.append(_str)

    if depth:
        _vals = _vals[:depth]
    _LOGGER.debug(' - VALS %s', _vals)

    return ''.join(_vals)


def strftime(fmt=None, time_=None):
    """Return a formatted string for the given time format + time.

    NOTE:

    This has an added %D feature which provides the day with
    its ordinal applied:

        eg. strftime('%a %D %b') -> 'Tue 10th Jan'

    And %P which provides the am/pm in lower case:

        eg.  strftime('%H:%M%P') -> '09:31am'

    Args:
        fmt (str): time format (eg. %H:%M:%S) or preset:
            default/path - clean/sortable style (eg. 240905_101414)
            nice - simple readable format (eg. 05/09/24 10:14:14)
            full - full readable format (eg. Fri 05/09/24 10:14:14)
            date - just date (eg. 05/09/24)
            time - just time (eg. 10:14:14)
        time_ (float|struct_time): time value

    Returns:
        (str): formatted time string
    """
    from pini.utils import to_ord

    if fmt == 'nice':
        _fmt = '%d/%m/%y %H:%M:%S'
    elif fmt == 'full':
        _fmt = '%a %d/%m/%y %H:%M:%S'
    elif fmt in (None, 'default', 'path'):
        _fmt = '%y%m%d_%H%M%S'
    elif fmt == 'date':
        _fmt = '%d/%m/%y'
    elif fmt == 'time':
        _fmt = '%H:%M:%S'
    else:
        _fmt = fmt

    _time = time_ or time.time()
    if '%D' in _fmt:
        _day = int(time.strftime('%d', to_time_t(_time)))
        _nice_day = f'{_day:d}{to_ord(_day)}'
        _fmt = _fmt.replace('%D', _nice_day)
    if '%P' in _fmt:
        _token = strftime('%p', time_).lower()
        _fmt = _fmt.replace('%P', _token)

    return time.strftime(_fmt, to_time_t(_time))


def to_time_f(val):
    """Get a time float from the given value.

    Args:
        val (float|struct_time): value to convert

    Returns:
        (float): time as float
    """
    if isinstance(val, (int, float)):
        return float(val)
    if isinstance(val, time.struct_time):
        return time.mktime(val)
    if isinstance(val, datetime.datetime):
        if sys.version_info.major == 3:
            return val.timestamp()
        if sys.version_info.major == 2:
            return time.mktime(val.timetuple()) + val.microsecond / 1e6
        raise NotImplementedError(sys.version_info.major)
    if isinstance(val, str):
        return to_time_f(to_time_t(val))
    raise NotImplementedError(f'Failed to map {type(val).__name__} - {val}')


def to_time_t(val=None):
    """Get a time tuple from the given value.

    Args:
        val (float|struct_time): value to convert

    Returns:
        (struct_time): time tuple
    """
    if val is None:
        return time.localtime()
    if isinstance(val, (int, float)):
        return time.localtime(val)
    if isinstance(val, time.struct_time):
        return val
    if isinstance(val, datetime.datetime):
        return val.timetuple()

    # Convert from string
    if isinstance(val, str):
        for _fmt in (
                '%d/%m/%y',
                '%d/%m/%y %H:%M',

                '%y%m%d',
                '%y%m%d %H:%M',

                '%Y-%m-%d',
                '%Y-%m-%d %H:%M',
                '%Y-%m-%dT%H:%M:%SZ',
                '%Y-%m-%dT%H:%M:%S.%fZ',
        ):
            try:
                return time.strptime(val, _fmt)
            except ValueError:
                pass
        raise NotImplementedError(f'Failed to convert time string "{val}"')

    raise NotImplementedError(val)
