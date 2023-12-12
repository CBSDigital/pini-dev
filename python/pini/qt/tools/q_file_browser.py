"""Tools for managing the pini file browser."""

import logging

from pini.utils import to_str, abs_path, File, Dir, file_to_seq

from ..q_mgr import QtWidgets
from .. import q_utils

_LOGGER = logging.getLogger(__name__)


def file_browser(root='~', mode='ExistingFile', extn=None, title=None):
    """Launch a file browser dialog.

    Args:
        root (str): directory to start browser in
        mode (str): type of result required
        extn (str): apply file extension filter
        title (str): override browser window title

    Returns:
        (Path): selected path
    """
    q_utils.get_application()

    _LOGGER.debug('FILE BROWSER')
    _root = abs_path(to_str(root or '~'))
    _LOGGER.debug(' - ROOT %s', _root)

    if mode == 'ExistingFile':
        _filter = None
        if extn:
            _filter = '*.{}'.format(extn)
        _title = title or 'Select File'
        _path, _filter = QtWidgets.QFileDialog.getOpenFileName(
            dir=_root, caption=_title, filter=_filter)
        _LOGGER.debug(' - DIALOG "%s" "%s"', _path, _filter)
        if not _path:
            raise q_utils.DialogCancelled
        _result = File(_path)

    elif mode == 'ExistingDir':
        _path = QtWidgets.QFileDialog.getExistingDirectory(
            dir=_root, caption='Select Directory')
        _result = Dir(_path)

    elif mode == 'ExistingSeq':
        _title = title or 'Select Sequence File'
        _path, _filter = QtWidgets.QFileDialog.getOpenFileName(
            dir=_root, caption=_title)
        _LOGGER.debug(' - DIALOG "%s" "%s"', _path, _filter)
        if not _path:
            raise q_utils.DialogCancelled
        _result = file_to_seq(_path, safe=False)

    elif mode == 'SaveFile':
        raise NotImplementedError(mode)

    else:
        raise NotImplementedError(mode)

    _LOGGER.debug(' - RESULT %s', _result)

    return _result
