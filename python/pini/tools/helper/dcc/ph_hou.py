"""Tools for managing the houdini PiniHelper."""

import logging

from pini.utils import wrap_fn

from hou_pini import h_pipe

from .. import ph_window, ph_utils

_LOGGER = logging.getLogger(__name__)


class HouPiniHelper(ph_window.PiniHelper):  # pylint: disable=abstract-method,too-many-ancestors
    """PiniHelper dialog for houdini."""

    def _context__SOutputs(self, menu):
        _out = self.ui.SOutputs.selected_data()
        super()._context__SOutputs(menu)
        menu.add_separator()
        if _out.type_ == 'ass_gz':
            menu.add_action(
                'Import shaders',
                wrap_fn(h_pipe.import_assgz_shaders, out=_out, parent=self),
                icon=ph_utils.LOOKDEV_BG_ICON)
