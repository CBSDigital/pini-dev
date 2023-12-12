"""Tools for managing PySide or PySide imports transparently."""

# pylint: disable=unused-import

import logging
import os

_LOGGER = logging.getLogger(__name__)
_FORCE = os.environ.get('PINI_QT_LIB')
_SUCCESS = False
LIB = None

# Try to import qt mods from PySide2
if (_FORCE and _FORCE == 'PySide2') or not _SUCCESS:
    try:
        from PySide2 import QtUiTools, QtCore, QtGui, QtWidgets
        from PySide2.QtCore import Qt
    except ImportError as _exc:
        _LOGGER.debug('FAILED TO LOAD PySide2 %s', _exc)
    else:
        _SUCCESS = True
        LIB = 'PySide2'

# Try to import qt mods from PySide
if (_FORCE and _FORCE == 'PySide') or not _SUCCESS:
    try:
        from PySide import QtUiTools, QtCore, QtGui
        _LOGGER.debug('LOADED QtUiTools, QtCore, QtGui')
        from PySide import QtGui as QtWidgets
        _LOGGER.debug('LOADED QtWidgets')
        from PySide.QtCore import Qt
        _LOGGER.debug('LOADED Qt')
    except ImportError as _exc:
        _LOGGER.debug('FAILED TO LOAD PySide %s', _exc)
    else:
        _SUCCESS = True
        LIB = 'PySide'

# Try to import qt mods from PySide6
if (_FORCE and _FORCE == 'PySide6') or not _SUCCESS:
    try:
        from PySide6 import QtUiTools, QtWidgets, QtCore, QtGui
        from PySide6.QtCore import Qt
        _LOGGER.debug('LOADED Qt')
    except ImportError as _exc:
        _LOGGER.debug('FAILED TO LOAD PySide6 %s', _exc)
    else:
        _SUCCESS = True
        LIB = 'PySide6'

# Try to import qt mods from PyQt5
if (_FORCE and _FORCE == 'PyQt5') or not _SUCCESS:
    try:
        from PyQt5 import QtCore, QtGui, QtWidgets, uic as QtUiTools
        from PyQt5.QtCore import Qt
    except ImportError:
        _LOGGER.debug('FAILED TO LOAD PyQt5')
    else:
        _SUCCESS = True
        LIB = 'PyQt5'

# Try to import qt mods from PyQt4
if (_FORCE and _FORCE == 'PyQt4') or not _SUCCESS:
    try:
        from PyQt4 import QtCore, QtGui
        from PyQt4 import QtGui as QtWidgets
        from PyQt4.QtCore import Qt
    except ImportError:
        _LOGGER.debug('FAILED TO LOAD PyQt4')
    else:
        _SUCCESS = True
        LIB = 'PyQt4'

if not _SUCCESS:
    raise ImportError('Failed to import qt')
