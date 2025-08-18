"""Tools for managing a dockable maya mixin defined by a ui file."""

import logging

from . import qc_ui_base, qc_mixin

_LOGGER = logging.getLogger(__name__)


class CUiDockableMixin(qc_mixin.CDockableMixin, qc_ui_base.CUiBaseDummy):
    """Dockable maya interface defined by a ui file."""

    def __init__(self, ui_file, catch_errors=True, show=True, parent=None,
                 store_settings=True, stack_key=None, title=None):
        """Constructor.

        Args:
            ui_file (str): path to ui file
            catch_errors (bool): catch errors
            show (bool): show on launch
            parent (QDialog): override parent ui
            store_settings (bool): load settings on launch
            stack_key (str): override dialog stack key
            title (str): override title
        """
        super().__init__(
            parent=parent, show=show, title=title)
        qc_ui_base.CUiBase.__init__(
            self, ui_file=ui_file, show=False, catch_errors=catch_errors,
            store_settings=store_settings, stack_key=stack_key)

    def delete(self):
        """Delete this interface."""
        _LOGGER.debug('DELETE')
        super().delete()
        qc_ui_base.CUiBase.delete(self)
        _LOGGER.debug(' - DELETE COMPLETE')
