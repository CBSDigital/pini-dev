"""Miscellaneous utilities."""

import copy
import datetime
import getpass
import os
import logging
import inspect
import math
import platform
import random
import subprocess
import time
import types

import six

_LOGGER = logging.getLogger(__name__)
_EXES = {}


class SimpleNamespace(object):
    """A simple empty object which can have attributes added.

    Keyword arguments are added as attributes on init - eg:

        >>> _test = SimpleNamespace(blah=1)
        >>> print _test.blah
        1
    """

    def __init__(self, **kwargs):
        """Constructor."""
        for _name, _val in kwargs.items():
            setattr(self, _name, _val)

    def __bool__(self):
        return False

    def __repr__(self):
        _name = getattr(self, 'name', type(self).__name__)
        return '<{}>'.format(_name)


# Empty object used to denote a variable not having been set - this is useful
# if None is a valid value for a variable
EMPTY = SimpleNamespace(name='EMPTY')


def basic_repr(obj, label, show_nice_id=None, separator=':'):
    """Basic object __repr__ function.

    Returns a basic print string with the type and a label in angle brackets.

    Args:
        obj (any): object to obtain type from
        label (str): object label
        show_nice_id (str): include object id in a readable form
        separator (str): override separator character (default is :)

    Returns:
        (str): print string
    """

    # Determine nice id
    _show_nice_id = show_nice_id
    if _show_nice_id is None:
        _show_nice_id = os.environ.get('PINI_REPR_NICE_IDS')

    # Build string
    _str = '<' + type(obj).__name__.strip('_')
    if _show_nice_id:
        _str += '[{}]'.format(nice_id(obj))
    if label:
        _str += separator+str(label)
    _str += '>'

    return _str


def bytes_to_str(bytes_):
    """Convert a number of bytes to a readable string.

    eg. 2000 -> 2k

    Args:
        bytes_ (int): number of bytes

    Returns:
        (str): bytes as readable string
    """
    _size = float(bytes_)
    _labels = ["B", "K", "M", "G", "T", "P"]
    _factor = 0
    while _size > 1000:
        _factor += 1
        _size /= 1000
        if _factor > 5:
            raise RuntimeError("Could not convert: {:d}".format(bytes_))
    if _size == 0:
        return "0"
    _size = "{:.02f}".format(_size)
    return _size + _labels[_factor]


def dprint(*args, **kwargs):
    """Print the given data with a clock prefix."""
    if not kwargs.get('verbose', True):
        return
    print(strftime('[%H:%M:%S] ') + ' '.join([str(_arg) for _arg in args]))


def fr_enumerate(data, last_=True):
    """Enumerate the given list with fractional values.

    eg.

    fr_enumerate(range(3)) -> [(0.0, 0), (0.5, 1), (1.0, 2)]
    fr_enumerate(range(3), last_=False) -> [(0.0, 0), (0.333, 1), (1.666, 2)]

    Args:
        data (list): data to enumerate
        last_ (bool): include the last value (ie. 1.0) or skip this one

    Returns:
        (list): zipped list
    """
    _list = data
    if isinstance(_list, enumerate):
        _list = list(_list)
    return zip(fr_range(len(_list), last_=last_), _list)


def fr_range(count, last_=True):
    """Build a range of fractions from 0 to 1.

    eg. fr_range(3) -> [0.0, 0.5, 1.0]
        fr_range(3, last_=False) -> [0.0, 0.333, 0.666]

    Args:
        count (int): number of items in range
        last_ (bool): include the last value (ie. 1.0) in the list

    Returns:
        (float list): list of fractions
    """
    if count == 1:
        return [0]
    _end = count-1 if last_ else count
    return [1.0*_idx/_end for _idx in range(count)]


def get_user():
    """Get the current username.

    This can be override using the $PINI_USER var.

    Returns:
        (str): username
    """
    return os.environ.get('PINI_USER', getpass.getuser())


def ints_to_str(ints):
    """Express a list of integers as a readable string (eg. '1-10').

    Args:
        ints (int list): intergers to convert

    Returns:
        (str): readable string
    """
    _LOGGER.debug('STR TO INTS %s', ints)
    _str = ''
    for _idx, _int in enumerate(ints):
        _last = _idx == len(ints) - 1
        _LOGGER.debug(' - ADDING idx=%d idx=%d last=%d str=%s',
                      _idx, _int, _last, _str)
        if not _idx:
            _str += str(_int)
        elif ints[_idx-1] != _int-1:
            _str += ',{}'.format(_int)
        elif not _last and ints[_idx-1] == _int-1 and ints[_idx+1] == _int+1:
            pass
        else:
            _str += '-{}'.format(_int)
        # elif _last:
        #     _str += str(_int)
        # if not _str.endswith('-'):
        #     _str += '-'
    # _str = _str.rstrip('-')
        _LOGGER.debug('   - STR %s', _str)
    _LOGGER.debug('STR %s', _str)
    return _str


def last(items):
    """Enumerator which marks the last item of a list of items.

    eg. last([1, 2, 3]) -> [(False, 1), (False, 2), (True, 3)]

    Args:
        items (list): list of items

    Returns:
        (list): list of data pairs
    """
    from .u_six import SixIterable
    _items = items
    if isinstance(_items, (enumerate, SixIterable)):
        _items = list(_items)
    _last_idx = len(_items) - 1
    return [(_idx == _last_idx, _item) for _idx, _item in enumerate(_items)]


def lprint(*args, **kwargs):
    """Print the given data to the console.

    This provides a print function which behaves the same in python 2/3
    and which can be supressed using the verbose flag, avoiding too many
    if statements.

    Args:
        verbose (bool): if False do not print
    """
    if not kwargs.get('verbose', True):
        return
    print(' '.join([str(_arg) for _arg in args]))


def merge_dicts(dict_a, dict_b):
    """Merge two dictionaries.

    If any values in the tree are dictionaries, they will also be merged.

    Keys in the second dictionary take precedence over the ones in the
    first dictionary.

    Args:
        dict_a (dict): base dictionary
        dict_b (dict): dict to update with

    Returns:
        (dict): merged dict
    """
    _keys = set()
    _keys.update(dict_a)
    _keys.update(dict_b)

    _result = {}
    for _key in _keys:

        if _key in dict_a and _key not in dict_b:
            _val = copy.deepcopy(dict_a[_key])
        elif _key in dict_b and _key not in dict_a:
            _val = copy.deepcopy(dict_b[_key])
        else:
            _val_a = dict_a[_key]
            _val_b = dict_b[_key]
            if isinstance(_val_a, dict) and isinstance(_val_b, dict):
                _val = merge_dicts(_val_a, _val_b)
            else:
                _val = copy.deepcopy(_val_b)

        _result[_key] = _val

    return _result


def nice_age(age, depth=None, pad=None, weeks=True, seconds=True):
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
    _LOGGER.debug('NICE AGE')
    _str = ''
    _secs = int(age)
    _depth = 0
    _fmt = '{:d}' if not pad else '{{:0{:d}d}}'.format(pad)

    # Add weeks
    if weeks and _secs > 7*24*60*60 and (depth is None or _depth < depth):
        _wks = int(_secs/(7*24*60*60))
        _secs = _secs - _wks*7*24*60*60
        _str += (_fmt+'w').format(_wks)
        _depth += 1

    # Add days
    if _secs > 24*60*60 and (depth is None or _depth < depth):
        _days = int(_secs/(24*60*60))
        _secs = _secs - _days*24*60*60
        _str += (_fmt+'d').format(_days)
        _depth += 1

    # Add hours
    if _str or _secs > 60*60 and (depth is None or _depth < depth):
        _hours = int(_secs/(60*60))
        _str += (_fmt+'h').format(_hours)
        _secs = _secs - _hours*60*60
        _depth += 1
        _LOGGER.debug(' - ADDED HOURS %s (secs=%d)', _str, _secs)

    # Add mins
    if depth is not None and _depth >= depth:  # depth filters
        pass
    elif (
            (_str and _secs) or  # secs left but no minutes
            _secs > 60):
        _mins = int(_secs/60)
        _str += (_fmt+'m').format(_mins)
        _secs = _secs - _mins*60
        _depth += 1
        _LOGGER.debug(' - ADDED MINS %s', _str)

    # Add secs
    if seconds and depth is None or _depth < depth:
        _str += (_fmt+'s').format(_secs)
        _LOGGER.debug(' - ADDED SECS %s', _str)

    return _str


def nice_id(obj):
    """Express an object's memory address in a readable form.

    eg. 2377640966808L -> NoHiBlue
        2377641589000L -> MinMinNah

    This is to assist debugging.

    Args:
        obj (object): object to read address of

    Returns:
        (str): readable unique string
    """
    _words = [
        'Blee', 'Blue', 'Ga', 'Go', 'Hi', 'Ho', 'Hop', 'Jot', 'Lak',
        'Min', 'Nah', 'No', 'Pie', 'Pop', 'Pu', 'Ro', 'See',
        'Wa', 'Wo', 'Wu', 'Zo']
    _id = id(obj)
    _rand = str_to_seed(str(_id))
    return ''.join([_rand.choice(_words) for _ in range(3)])


def nice_size(bytes_):
    """Express a size in bytes in a readable form.

    eg. 11100 -> 11.1 KB

    Args:
        bytes_ (int): size in raw bytes

    Returns:
        (str): size in a readable form
    """
    if bytes_ == 0:
        return "0B"
    _name = ("B", "KB", "MB", "GB", "TB", "PB", "EB", "ZB", "YB")
    _idx = int(math.floor(math.log(bytes_, 1000)))
    _pow = math.pow(1000, _idx)
    _size = round(bytes_ / _pow, 2)
    return ''.join([str(_size), _name[_idx]])


def null_dec(func):
    """Build a decorator that does nothing.

    Useful for substituting a decorator which isn't available.

    Args:
        func (fn): function to decorate

    Returns:
        (fn): null decorator
    """
    return func


def read_func_kwargs(func, args, kwargs):
    """Map a function's args/kwargs to a simple list of kwargs.

    This can be used in a decorator to determine the value of an arg/kwarg,
    whether it has been passed as an arg or a kwargs.

    Args:
        func (fn): function to read signature from
        args (list): argument values
        kwargs (dict): keyword argument values

    Returns:
        (dict): combined args + kwargs data
    """
    _LOGGER.debug('READ FUNC KWARGS %s %s %s', func, args, kwargs)

    _spec = inspect.getfullargspec(func)
    _defaults = _spec.defaults or []
    _LOGGER.debug(' - DEFAULTS %s', _defaults)
    _args = list(_spec.args)
    _LOGGER.debug(' - ARGS %s', _args)

    _kwargs = {}
    for _idx, _arg_name in enumerate(_args):
        _LOGGER.debug('ARG %s %s', _arg_name, _idx)
        _arg_idx = _idx - len(_args)

        if _idx < len(args):
            _val = args[_idx]
        elif _arg_name in kwargs:
            _val = kwargs[_arg_name]
        elif abs(_arg_idx) > len(_defaults):
            _LOGGER.info('ARGS %s %s', _spec.args, _args)
            _LOGGER.info('DEFAULTS %s %s', _spec.defaults, _defaults)
            raise TypeError(
                'It looks like some of the required args are '
                'missing {}'.format(func.__name__))
        else:
            _val = _defaults[_arg_idx]

        # For self arg use object id
        if _idx == 0 and _arg_name == 'self' and isinstance(_val, object):
            _val = id(_val), _val

        _kwargs[_arg_name] = _val

    return _kwargs


def safe_zip(*lists):
    """Zip together multiple lists, erroring if they are not same length.

    Returns:
        (tuple list): zipped lists

    Raises:
        (ValueError): if lists are not all the same length
    """
    assert len(lists) >= 2
    for _idx, _list in enumerate(lists[1:]):
        if not len(lists[0]) == len(_list):
            raise ValueError(
                'Length of list {:d} ({:d}) does not match length of list 1 '
                '({:d})'.format(_idx+2, len(_list), len(lists[0])))

    return zip(*lists)


def single(
        items, catch=False, items_label='items', error=None,
        zero_error=None, multi_error=None, verbose=0):
    """Obtain a single value from a list.

    This will fail if there is not exactly one value in the list.

    Args:
        items (list): list of data to take item from
        catch (bool): no error if there is not exactly one value
            (just return None instead)
        items_label (str): name for items in logging/errors (eg. handlers)
        error (str): override error message on fail
        zero_error (str): override error message if no items are found
        multi_error (str): override error message if multiple items are found
        verbose (int): print process data

    Returns:
        (any): single item

    Raises:
        (ValueError): if there was not exactly one item in the list
    """
    _LOGGER.debug('SINGLE type=%s %s', type(items), items)

    # Obtain item list
    _items = items
    if isinstance(_items, (set, types.GeneratorType)):
        _items = tuple(_items)

    # Handle fail
    if len(_items) != 1:
        if catch:
            return None
        if verbose:
            _LOGGER.info('MATCHED %d %s', len(_items), items_label.upper())
            for _item in _items:
                _LOGGER.info(' - %s', _item)
        if not _items:
            _error = (
                zero_error or error or
                'No {} found'.format(items_label))
        else:
            _error = (
                multi_error or error or
                'Multiple {} found'.format(items_label))
        raise ValueError(_error)
    return _items[0]


def strftime(fmt=None, time_=None):
    """Return a formatted string for the given time format + time.

    NOTE: this has an added %D feature which provides the day with
    it's ordinal applied

        eg. strftime('%a %D %b') -> 'Tue 10th Jan'

    Args:
        fmt (str): time format (eg. %H:%M:%S)
        time_ (float/struct_time): time value

    Returns:
        (str): formatted time string
    """
    from pini.utils import to_ord

    _time = time_ or time.time()
    _fmt = fmt or '%y%m%d_%H%M%S'
    if '%D' in _fmt:
        _day = int(time.strftime('%d', to_time_t(_time)))
        _nice_day = '{:d}{}'.format(_day, to_ord(_day))
        _fmt = _fmt.replace('%D', _nice_day)
    if '%P' in _fmt:
        _token = strftime('%p', time_).lower()
        _fmt = _fmt.replace('%P', _token)
    return time.strftime(_fmt, to_time_t(_time))


def str_to_ints(string, chunk_sep=",", rng_sep="-", end=None, inc=1):
    """Convert a string to a list of integers.

    eg. '1-5,10' will return [1, 2, 3, 4 5, 10]

    Args:
        string (str): string to convert
        chunk_sep (str): override chunk separator
        rng_sep (str): overrde range separator
        end (int): range maxium (required for open range eg. '1-')
        inc (int): range increment

    Returns:
        (int list): integer values
    """
    from pini import dcc

    if not string:
        return []

    _end = end
    if _end is None and dcc.NAME:
        _end = dcc.t_end(int)

    _ints = []
    for _rng in string.split(chunk_sep):

        if not _rng:
            continue

        # Handle inc
        _inc = inc
        if "x" in _rng:
            assert _rng.count("x") == 1
            _rng, _inc = _rng.split("x")
            _inc = int(_inc)

        # Handle range
        _single_neg = (
            rng_sep == '-' and _rng.startswith('-') and _rng.count('-') == 1)
        if rng_sep in _rng and not _single_neg:

            # Read tokens
            _split = _rng.rfind(rng_sep)
            _tokens = [
                int(float(_val)) if _val else None
                for _val in (_rng[: _split], _rng[_split+1:])]

            # Convert to list of ints
            if _rng.endswith(rng_sep):
                _rng_start = _tokens[0]
                _rng_end = _end
                if not _end:
                    raise ValueError('No end found')
            else:
                _rng_start = _tokens[0]
                _rng_end = _tokens[-1]
            _ints += list(range(_rng_start, _rng_end+1, _inc))

        # Handle lone num
        else:
            _ints.append(int(_rng))

    return _ints


def str_to_seed(string, offset=0):
    """Build a Random object with seed based on the given string.

    Args:
        string (str): string to generate seed from
        offset (int): apply seed offset

    Returns:
        (Random): seeded random object
    """
    _random = random.Random()
    if not isinstance(string, six.string_types):
        raise ValueError('Not string {} ({})'.format(string, type(string)))
    _total = offset
    for _idx, _chr in enumerate(string):
        _random.seed(ord(_chr)*(_idx+1))
        _total += int(_random.random()*100000)
    _random.seed(_total)
    _LOGGER.debug('STR TO SEED total=%d', _total)
    return _random


def system(
        cmd, result=True, decode='utf-8', block_shell_window=True, verbose=0):
    """Execute a system command.

    Args:
        cmd (str): command to execute
        result (bool): whether to wait + return result
            True|out - return stdout
            out/err - return stout/stderr as tuple
        decode (str): encoding to decode bytes result with
            (default is utf-8)
        block_shell_window (bool): prevent shell window from appearing
            (windows only)
        verbose (int): print process data

    Returns:
        (str|tuple|None): result (if requested)
    """
    from pini.utils import Path, Seq, clip

    if isinstance(cmd, list):
        _cmds = cmd
    else:
        _cmds = []
        if platform.system() == 'Windows':
            _cmds += ["cmd", "/C"]
        _cmds += cmd.split()
    _cmds = [
        _item.path if isinstance(_item, (Path, Seq, clip.Seq))
        else str(_item)
        for _item in _cmds]
    if verbose:
        _LOGGER.info(' '.join([
            '"{}"'.format(_cmd) if ' ' in _cmd else _cmd
            for _cmd in _cmds]))

    # Execute command
    _si = None
    if block_shell_window and platform.system() == 'Windows':
        _si = subprocess.STARTUPINFO()
        _si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    _pipe = subprocess.Popen(
        _cmds,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        startupinfo=_si)
    if not result:
        return None

    # Process results
    _out, _err = _pipe.communicate()
    if decode and isinstance(_out, bytes):
        _out = _out.decode(decode)
    if decode and isinstance(_err, bytes):
        _err = _err.decode(decode)

    # Handle result
    if result in [True, 'out']:
        return _out
    if result == 'out/err':
        return _out, _err
    if result == 'err':
        return _err
    raise ValueError(result)


def to_time_f(val):
    """Get a time float from the given value.

    Args:
        val (float/struct_time): value to convert

    Returns:
        (float): time as float
    """
    if isinstance(val, (int, float)):
        return float(val)
    if isinstance(val, time.struct_time):
        return time.mktime(val)
    if isinstance(val, datetime.datetime):
        return val.timestamp()
    raise NotImplementedError('Failed to map {} - {}'.format(
        type(val).__name__, val))


def to_str(obj):
    """Convert the given object to a string.

    eg. to_str(File('/tmp/test.file')) -> '/tmp/test.file'
        to_str('/tmp/test.file') -> '/tmp/test.file'

    Args:
        obj (any): object to read string from

    Returns:
        (str): object as a string
    """
    from pini.utils import Path, Seq

    if obj is None:
        return ''
    if isinstance(obj, (Path, Seq)):
        return obj.path
    if isinstance(obj, six.string_types):
        return obj
    if isinstance(obj, (float, int)):
        return str(obj)

    raise NotImplementedError(
        '{} ({})'.format(obj, type(obj).__name__))


def to_time_t(val):
    """Get a time tuple from the given value.

    Args:
        val (float|struct_time): value to convert

    Returns:
        (struct_time): time tuple
    """
    if isinstance(val, (int, float)):
        return time.localtime(val)
    if isinstance(val, time.struct_time):
        return val
    raise ValueError(val)


def val_map(val, in_min=0.0, in_max=1.0, out_min=0.0, out_max=1.0):
    """Map a value from one range to another one.

    Args:
        val (float): value to map
        in_min (float): input range minimum
        in_max (float): input range maximum
        out_min (float): output range minimum
        out_max (float): output range maximum

    Returns:
        (float): mapped value
    """
    assert isinstance(in_min, (int, float))
    assert isinstance(in_max, (int, float))
    assert isinstance(out_min, (int, float))
    assert isinstance(out_max, (int, float))
    if in_min == in_max:
        assert val == in_min
        return out_min
    _in_span = in_max - in_min
    _out_span = out_max - out_min
    _val_scaled = float(val - in_min) / float(_in_span)
    return out_min + (_val_scaled * _out_span)
