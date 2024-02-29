"""Tools for managing the houdini blast/flipbook handler."""

import logging

from hou_pini import h_pipe

from . import bh_base

_LOGGER = logging.getLogger(__name__)


class CHouFlipbook(bh_base.CBlastHandler):
    """Blast/Flipbook handler for houdini."""

    NAME = 'Flipbook Tool'
    LABEL = 'Flipbooks the current scene'

    def blast(self):
        """Excute flipbook."""
        _view = self.ui.View.isChecked()
        _fmt = self.ui.Format.currentText()
        _rng = self._read_range()
        _burnins = self.ui.Burnins.isChecked()
        _force = self.ui.Force.isChecked()
        _LOGGER.info('BLAST view=%d format=%s range=%s', _view, _fmt, _rng)
        h_pipe.flipbook(
            format_=_fmt, view=_view, range_=_rng, burnins=_burnins,
            force=_force)
