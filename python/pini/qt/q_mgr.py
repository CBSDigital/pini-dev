"""Tools for managing PySide or PySide imports transparently."""

# pylint: disable=unused-import

import logging
import os
import sys

from pini import dcc


_LOGGER = logging.getLogger(__name__)
_FORCE = os.environ.get('PINI_QT_LIB')


def _import_mod(name):
    """Import a module using its name.

    Args:
        name (str): module name (eg. PySide6.QtCore)

    Returns:
        (mod): imported module
    """
    return __import__(name, fromlist=[name])


def _load_pyside():
    """Load PySide modules.

    Returns:
        (tuple): pyside, shiboken
    """

    # Determine which version to try
    if _FORCE:
        if not _FORCE.startswith('PySide'):
            raise NotImplementedError(_FORCE)
        _ver = int(_FORCE[-1])
        _sort = [_ver]
    elif dcc.NAME:
        _sort = [2, 6]
    else:
        _sort = [6, 2]

    # Attempt to load version
    for _ver in _sort:
        try:
            _pyside = _import_mod(f'PySide{_ver}')
            _shiboken = _import_mod(f'shiboken{_ver}')
        except ImportError:
            continue
        return _pyside, _shiboken

    raise ImportError('Failed to load any PySide version')


CORE, shiboken = _load_pyside()
LIB = CORE.__name__
LIB_VERSION = CORE.__version__

QtCore = _import_mod(f'{LIB}.QtCore')
QtGui = _import_mod(f'{LIB}.QtGui')
QtUiTools = _import_mod(f'{LIB}.QtUiTools')
QtWidgets = _import_mod(f'{LIB}.QtWidgets')

Qt = QtCore.Qt
