"""General testing tools."""

import functools
import inspect
import logging
import os
import sys

from pini import icons, dcc
from pini.utils import (
    check_heart, TMP, Image, abs_path, PyFile, strftime, File)

_LOGGER = logging.getLogger(__name__)

TEST_YML = TMP.to_file('test.yml')
TEST_DIR = TMP.to_subdir('PiniTesting')


def clear_print(text):
    """Print the given text with start/end pipes to show spaces.

    Args:
        text (str): text to print
    """
    print('|' + '|\n|'.join(text.split('\n')) + '|')


def dev_mode():
    """Check whether pini dev mode is enabled.

    Returns:
        (bool): whether currently in dev mode
    """
    return os.environ.get('PINI_DEV') == '1'


def obt_image(extn='exr'):
    """Obtain a valid tmp image file of the given format for testing.

    Args:
        extn (str): file format

    Returns:
        (File): image file
    """
    _file = TMP.to_file(base='tmp', extn=extn)
    if not _file.exists():

        _src = Image(icons.find('Green Apple'))
        _src.convert(_file)

    assert _file.exists()

    return _file


def _to_code_str(val):
    """Convert the given attribute value to a printable string.

    eg. 1 -> '1'
        "blah" -> '"blah"'
        0.12 -> '0.12'

    Args:
        val (str): value to convert

    Returns:
        (str): code string
    """
    if isinstance(val, str):
        return f'"{val}"'
    if isinstance(val, (bool, int, float)):
        return f'{val}'
    raise NotImplementedError(val, type(val))


def print_exec_code(func, mod=None):
    """Decorator which prints the code to execute this function.

    This includes the value of any args/kwargs.

    Args:
        func (fn): function to decorate
        mod (mod): parent module

    Returns:
        (fn): decorated function
    """

    @functools.wraps(func)
    def _print_exec_code_fn(*args, **kwargs):
        _LOGGER.info('PRINT EXEC CODE %s', func)

        # Determine module info + import str
        _mod = mod
        if not _mod:
            _file = abs_path(inspect.getfile(func))
            _LOGGER.debug(' - FILE %s', _file)
            _mod = PyFile(_file).to_module()
            _LOGGER.debug(' - MOD %s', _mod)
        _mod_name = _mod.__name__
        if '.' in _mod_name:
            _mod_parent, _mod_child = _mod_name.rsplit('.', 1)
            _import_s = f'from {_mod_parent} import {_mod_child}'
        else:
            _import_s = f'import {_mod_name}'

        # Build args str
        _args_s = ''
        for _arg in args:
            _arg_s = _to_code_str(_arg)
            _args_s += f'{_arg_s}, '
        for _key, _val in kwargs.items():
            _args_s += f'{_key}={_to_code_str(_val)}, '
        _args_s = _args_s.strip(', ')

        # Print code
        _code = '; '.join([
            _import_s,
            f'{_mod_name}.{func.__name__}({_args_s})'])
        _LOGGER.info(' - CODE %s', _code)

        _result = func(*args, **kwargs)
        return _result

    return _print_exec_code_fn


def set_dev_mode(value):
    """Set dev mode environment variable.

    Args:
        value (bool): value to apply
    """
    if value:
        os.environ['PINI_DEV'] = '1'
    else:
        del os.environ['PINI_DEV']


class _PStreamHandler(logging.StreamHandler):
    """Stream handler for pini.

    Defined here to allow it to be distinguished from other handlers.
    """


class _PFileHandler(logging.FileHandler):
    """File handler for pini.

    Defined here to allow it to be distinguished from other handlers.
    """


def setup_logging(file_=False, edit=False, flush='all', name=None):
    """Setup logging with a generic handler.

    Args:
        file_ (bool): apply logging to file
        edit (bool): edit log file
        flush (bool): remove existing handlers
        name (str): override log file label (default is dcc name)
    """
    _LOGGER.info('SETUP LOGGING')

    _logger = logging.getLogger()
    _logger.setLevel(logging.INFO)

    # Flush existing handlers
    if flush in (True, 'all'):
        while _logger.handlers:
            check_heart()
            _handler = _logger.handlers[0]
            _name = type(_handler).__name__
            _LOGGER.debug(
                ' - REMOVE HANDLER %s %d %s', _handler,
                isinstance(_handler, _PStreamHandler), _name)
            _logger.removeHandler(_handler)
    elif flush == 'pini':
        for _handler in list(_logger.handlers):
            _name = type(_handler).__name__
            if _name in (_PStreamHandler.__name__, _PFileHandler.__name__):
                _LOGGER.info(' - REMOVE HANDLER %s', _handler)
                _logger.removeHandler(_handler)
    elif flush is False:
        pass
    else:
        raise ValueError(flush)

    # Create handlers
    _handlers = []
    _stream_handler = _PStreamHandler(sys.stdout)
    _handlers.append(_stream_handler)
    if file_:
        _name = name or dcc.NAME
        _date_stamp = strftime('%y%m%d')
        _time_stamp = strftime('%H%M%S')
        _file = File(f'~/tmp/log/{_date_stamp}/{_time_stamp}_{_name}.log')
        _LOGGER.info(' - FILE %s', _file)
        _file.touch()
        if edit:
            _file.edit()
        _file_hander = _PFileHandler(_file.path)
        _handlers.append(_file_hander)
    _LOGGER.info(' - HANDLERS %d %s', len(_handlers), _handlers)

    # Setup handlers
    for _handler in _handlers:
        _formatter = logging.Formatter('- %(name)s: %(message)s')
        _handler.setFormatter(_formatter)
        _logger.addHandler(_handler)
