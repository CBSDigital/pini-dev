"""Tools for managing time ranges.

These are used to break up shotgrid requests into chunks, to avoid having
to keep re-reading old data.
"""

import datetime
import logging
import time

from pini.utils import strftime, check_heart, basic_repr, to_time_f

_LOGGER = logging.getLogger(__name__)


def build_ranges(start_t):
    """Build ranges from the given start time until now.

    First competed years are added, then completed months, then weeks going
    up to the current week of the month.

    Args:
        start_t (float): start time

    Returns:
        (SGCRange list): ranges
    """
    _rngs = []

    # Add completed years
    _year = int(strftime('%y', start_t))
    while True:
        check_heart()
        _start_s = '01/01/{:02d}'.format(_year)
        _LOGGER.debug(' - YEAR %s', _start_s)
        _year += 1
        _end_s = '01/01/{:02d}'.format(_year)
        _rng = SGCRange(
            datetime.datetime.strptime(_start_s, '%d/%m/%y'),
            datetime.datetime.strptime(_end_s, '%d/%m/%y'))
        _rngs.append(_rng)
        if _year >= int(strftime('%y')):
            break

    # Add completed months
    _month = 1
    while True:
        check_heart()
        _start_s = '01/{:02d}/{:02d}'.format(_month, _year)
        _LOGGER.debug(' - MONTH %s', _start_s)
        _month += 1
        _end_s = '01/{:02d}/{:02d}'.format(_month, _year)
        _rng = SGCRange(
            datetime.datetime.strptime(_start_s, '%d/%m/%y'),
            datetime.datetime.strptime(_end_s, '%d/%m/%y'))
        _rngs.append(_rng)
        if _month >= int(strftime('%m')):
            break

    # Add weeks
    _day = 1
    while True:
        check_heart()
        _start_s = '{:02d}/{:02d}/{:02d}'.format(_day, _month, _year)
        _end_s = _add_days(_start_s, 7)
        _rng = SGCRange(
            datetime.datetime.strptime(_start_s, '%d/%m/%y'),
            datetime.datetime.strptime(_end_s, '%d/%m/%y'))
        _label = '{} -> {}'.format(_start_s, _end_s)
        if _rng.end_t >= datetime.datetime.today():
            break
        _day = int(strftime('%d', _rng.end_t))
        _rngs.append(_rng)

    # Add days
    while True:
        check_heart()
        _start_s = '{:02d}/{:02d}/{:02d}'.format(_day, _month, _year)
        _end_s = _add_days(_start_s, 1)
        _rng = SGCRange(
            datetime.datetime.strptime(_start_s, '%d/%m/%y'),
            datetime.datetime.strptime(_end_s, '%d/%m/%y'))
        _label = '{} -> {}'.format(_start_s, _end_s)
        _rngs.append(_rng)
        if _rng.end_t >= datetime.datetime.today():
            break

    _LOGGER.debug(' - BUILT %d RANGES %s', len(_rngs), _rngs)

    return _rngs


def _add_days(date, days):
    """Add the given number of days to the given date.

    Args:
        date (str): date to add days to (eg. 29/07/81)
        days (int): number of days to add

    Returns:
        (str): updated date
    """
    _date_s = date
    _date_f = to_time_f(time.strptime(_date_s, '%d/%m/%y'))
    for _ in range(days):
        _date_f += 25*60*60  # 25 to account for clocks changing
        _date_s = strftime('%d/%m/%y', _date_f)

    return _date_s


class SGCRange(object):
    """Represents a time range (or point in time) to read shotgrid at."""

    def __init__(self, start_t, end_t=None):
        """Constructor.

        Args:
            start_t (float): range start
            end_t (float): range end
        """
        self.start_t = start_t
        self.end_t = end_t

        _fmt = '%d/%m/%y'
        self.label = '{} -> {}'.format(
            strftime(_fmt, self.start_t),
            strftime(_fmt, self.end_t))

    def to_tuple(self):
        """Obtain tuple of this range.

        Returns:
            (float tuple): start/end
        """
        return self.start_t, self.end_t

    def __repr__(self):
        return basic_repr(self, self.label)
