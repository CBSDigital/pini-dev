"""Tools for applying autofixes."""

import logging

from pini.utils import File, TMP, strftime

DIR = File(__file__).to_dir()

_LOGGER = logging.getLogger(__name__)


def _autofix_code(code):
    """AApply autofixes to the given code.

    Args:
        code (str): code to fix

    Returns:
        (str): fixed code
    """

    # Check code line by line
    _lines = []
    for _line in code.strip().split('\n'):

        _line = _line.rstrip()
        _tokens = _line.split()

        # Enforce double newline above def/class
        if (
                _tokens and
                _tokens[0] in ('def', 'class')):

            _LOGGER.debug(' - ADDING NEWLINES %s', _line)

            # Strip decorators
            _decs = []
            while _lines and _lines[-1] and (
                    _lines[-1][0] in ('@ ]})')):
                _decs.insert(0, _lines.pop())
            _LOGGER.debug('   - DECS %s', _decs)

            # Add newlines
            _n_lines = 1 if _line.startswith(' ') else 2
            _lines += [''] * _n_lines
            _LOGGER.debug('   - ADDED NEWLINES %s', _lines)
            _pop_idx = -1 - _n_lines
            while len(_lines) > 2 and _lines[_pop_idx] == '':
                _lines.pop(_pop_idx)
                _LOGGER.debug('   - CROPPED NEWLINES %s', _lines)
            _lines += _decs

        _lines.append(_line)

    _fixed = '\n'.join(_lines)
    if code:
        _fixed += '\n'

    return _fixed


def _save_updates(file_, code, force=False):
    """Save autofixes to file.

    Args:
        file_ (File): file to save to
        code (str): fixed code
        force (bool): apply updates without confirmation
    """
    _LOGGER.debug(' - AUTOFIXES WERE FOUND')

    # Apply bkp
    assert file_.dir[1] == ':'
    assert file_.dir[2] == '/'
    _t_stamp = strftime()
    _bkp = TMP.to_file(
        f'.pini/release/autofix/{file_.dir[3:]}/'
        f'{file_.base}_{_t_stamp}.{file_.extn}')
    _LOGGER.debug(' - BKP %s', _bkp.path)
    file_.copy_to(_bkp, force=True)

    # Apply updates
    _LOGGER.debug(' - UPDATING %s', file_.path)
    file_.write(code, wording='Apply autofixes?', diff=True, force=force)


def apply_autofix(file_, force=False):
    """Apply autofixes to the given code file.

    Args:
        file_ (File): file to read code from
        force (bool): apply updates without confirmation
    """
    _LOGGER.debug('APPLY AUTOFIX force=%d %s', force, file_.path)
    _orig = file_.read()
    _fixed = _autofix_code(_orig)
    if _orig != _fixed:
        _save_updates(file_, _fixed, force=force)
