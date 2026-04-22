"""Tools for managing terragen interaction via the pini.dcc module."""

import logging

import SyPy3 as SyPy  # pylint: disable=import-error

from pini.utils import abs_path, File

from .d_base import BaseDCC

_LOGGER = logging.getLogger(__name__)


class SyntheyesDCC(BaseDCC):
    """Manages interactions with syntheyes."""

    NAME = 'syntheyes'
    DEFAULT_EXTN = 'sni'
    VALID_EXTNS = ('sni', )

    _lev = None

    @property
    def lev(self):
        """Obtain syntheyes level.

        Returns:
            (SyLevel): level
        """
        if not self._lev:
            self._lev = SyPy.SyLevel()
            self._lev.OpenExisting()
        return self._lev

    def cur_file(self):
        """Get path to current file.

        Returns:
            (str|None): current file (if any)
        """
        _file = self.lev.SNIFileName()
        if not _file:
            return None
        return abs_path(_file)

    def _force_new_scene(self):
        """Force new scene."""
        self.lev.PerformActionByNameAndWait('Close')

    def _force_save(self, file_=None):
        """Force save the current scene without overwrite confirmation.

        Args:
            file_ (str): path to save scene to
        """
        if file_:
            _file = File(file_)
            self.lev.SetSNIFileName(_file.path)
        self.lev.PerformActionByNameAndWait('Save')
