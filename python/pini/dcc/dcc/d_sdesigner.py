"""Tools for managing substance designer interaction."""

# pylint: disable=import-error

import logging

import sd

from pini.utils import abs_path

from .d_base import BaseDCC

_LOGGER = logging.getLogger(__name__)


class SubstanceDesignerDCC(BaseDCC):
    """Manages interactions with substance."""

    NAME = 'sdesigner'
    DEFAULT_EXTN = 'sbs'
    VALID_EXTNS = 'sbs'

    def cur_file(self):
        """Get path to current file.

        Returns:
            (str): current file
        """
        _LOGGER.debug('FIND CURRENT SCENE')
        _ctx = sd.getContext()
        _LOGGER.debug(' - CTX %s', _ctx)
        _app = _ctx.getSDApplication()
        _LOGGER.debug(' - APP %s', _app)
        _ui = _app.getQtForPythonUIMgr()
        _LOGGER.debug(' - UI %s', _ui)
        _graph = _ui.getCurrentGraph()
        _LOGGER.debug(' - GRAPH %s', _graph)
        _pkg = _graph.getPackage()
        _LOGGER.debug(' - PKG %s', _pkg)
        _file = abs_path(_pkg.getFilePath())
        _LOGGER.debug(' - FILE %s', _file)
        return _file
