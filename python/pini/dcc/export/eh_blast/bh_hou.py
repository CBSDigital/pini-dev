"""Tools for managing the houdini blast/flipbook handler."""

import logging

from pini import pipe
from hou_pini import h_pipe

from . import bh_base

_LOGGER = logging.getLogger(__name__)


class CHouFlipbook(bh_base.CBlastHandler):
    """Blast/Flipbook handler for houdini."""

    NAME = 'Flipbook Tool'
    LABEL = 'Flipbooks the current scene'

    def _set_camera(self):
        """Set camera (not implemented in houdini)."""

    def _set_output_name(self):
        """Set output name (not implemented in houdini)."""

    def export(  # pylint: disable=unused-argument
            self, notes=None, version_up=False, snapshot=True, save=True,
            format_='mp4', view=True, range_=None, burnins=True,
            force_replace=False, run_checks=False, force=False):
        """Execute flipbook.

        Args:
            notes (str): export notes
            version_up (bool): version up after export
            snapshot (bool): take thumbnail snapshot on export
            save (bool): save work file on export
            format_ (str): blast format (eg. mp4/jpg)
            view (bool): view blast
            range_ (tuple): override range
            burnins (bool): apply burnins (mov only)
            force_replace (bool): replace existing without confirmation
            run_checks (bool): apply sanity check
            force (bool): force blast with no confirmation dialogs
        """
        _LOGGER.info('EXEC %s', self)
        _out = h_pipe.flipbook(
            format_=format_, view=view, range_=self.to_range(), burnins=burnins,
            save=False, force=force or force_replace, update_cache=False,
            update_metadata=False)
        return [pipe.CACHE.obt(_out)]
