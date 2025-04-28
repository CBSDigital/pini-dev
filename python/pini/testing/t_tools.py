"""General testing tools."""

import functools
import inspect
import logging
import os
import sys

from pini import icons
from pini.utils import check_heart, TMP, Image, abs_path, PyFile

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


def print_exec_code(func):
    """Decorator which prints the code to execute this function.

    This includes the value of any args/kwargs.

    Args:
        func (fn): function to decorate

    Returns:
        (fn): decorated function
    """

    @functools.wraps(func)
    def _print_exec_code_fn(*args, **kwargs):
        _LOGGER.info('PRINT EXEC CODE %s', func)

        # Determine module info
        _file = abs_path(inspect.getfile(func))
        _LOGGER.debug(' - FILE %s', _file)
        _mod = PyFile(_file).to_module()
        _LOGGER.debug(' - MOD %s', _mod)
        _mod_parent, _mod_name = _mod.__name__.rsplit('.', 1)

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
            f'from {_mod_parent} import {_mod_name}',
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


class _PiniHandler(logging.StreamHandler):
    """Logging handler for pini.

    Defined here to allow it to be distinguished from other handlers.
    """


def setup_logging(flush='all'):
    """Setup logging with a generic handler.

    Args:
        flush (bool): remove existing handlers
    """
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
                isinstance(_handler, _PiniHandler), _name)
            _logger.removeHandler(_handler)
    elif flush == 'pini':
        for _handler in list(_logger.handlers):
            _name = type(_handler).__name__
            if _name == _PiniHandler.__name__:
                _LOGGER.info(' - REMOVE HANDLER %s', _handler)
                _logger.removeHandler(_handler)
    elif flush is False:
        pass
    else:
        raise ValueError(flush)

    # Create default handler
    _handler = _PiniHandler(sys.stdout)
    _formatter = logging.Formatter(
        '- %(name)s: %(message)s')
    _handler.setFormatter(_formatter)
    _logger.addHandler(_handler)
