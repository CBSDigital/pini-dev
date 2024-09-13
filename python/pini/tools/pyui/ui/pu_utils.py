"""General utilities for python interfaces."""

import logging

from pini import qt, pipe
from pini.utils import Path, abs_path

_LOGGER = logging.getLogger()


def apply_browser_btn(mode, read_fn, set_fn):
    """Launch browser and apply its result to a field.

    Args:
        mode (str): browser mode (eg. ExistingFile)
        read_fn (fn): function to read field's current value
        set_fn (fn): function to apply value to field
    """
    _LOGGER.debug('BROWSER %s', mode)

    _root = None

    # Try to determine root from current path
    _cur_path = read_fn()
    if _cur_path:
        _cur_path = Path(abs_path(_cur_path))
        _LOGGER.debug(
            ' - CUR PATH %s exists=%d', _cur_path.path, _cur_path.exists())
        if _cur_path.exists():
            if not _cur_path.is_dir():
                _cur_path = _cur_path.to_dir()
            _root = _cur_path
        _LOGGER.info(' - ROOT FROM CUR PATH %s', _root)

    # Try and use current pipe dirs
    if not _root:
        for _root in [pipe.cur_work_dir(), pipe.cur_entity(), pipe.cur_job()]:
            if _root:
                break
        _LOGGER.info(' - ROOT FROM PIPE %s', _root)

    _result = qt.file_browser(mode=mode, root=_root)
    _LOGGER.debug(' - RESULT %s', _result)
    set_fn(_result.path)
