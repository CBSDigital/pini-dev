"""Tools for managing pini helper in nuke."""

import logging
import sys

import nuke
import nukescripts

from .. import ph_dialog

_LOGGER = logging.getLogger(__name__)


class NukePiniHelper(ph_dialog.PiniHelper):  # pylint: disable=abstract-method,too-many-ancestors
    """PiniHelper for nuke."""

    def __init__(self, parent=None):
        """Constructor.

        Args:
            parent (QWidget): parent widget
        """
        super().__init__(parent=parent, show=False)

    def delete(self):
        """Delete this pini helper instance."""
        _LOGGER.info('DELETE %s', self)
        _remove_existing_helper_panel()
        try:
            super().delete()
        except TypeError:
            _LOGGER.info('FAILED TO DELETE %s', self)

    def updateValue(self):  # pylint: disable=invalid-name
        """Seems to be required."""


def _remove_existing_helper_panel():
    """Remove any existing PiniHelper pane."""
    if not hasattr(sys, "PINI_HELPER_PANEL"):
        sys.PINI_HELPER_PANEL = None
    _LOGGER.info('REMOVE HELPER PANEL %s', sys.PINI_HELPER_PANEL)
    if sys.PINI_HELPER_PANEL:
        sys.PINI_HELPER_PANEL.destroy()
        sys.PINI_HELPER_PANEL = None
        _LOGGER.info('DESTROYED EXISTING PiniHelper')


def launch():
    """Launch nuke PiniHelper.

    Returns:
        (NukePiniHelper): dialog instance
    """
    from ... import helper

    # Clean existing
    if helper.DIALOG:
        helper.DIALOG.delete()
        helper.DIALOG = None
    _remove_existing_helper_panel()

    # Launch PiniHelper as nuke panel
    sys.PINI_HELPER_PANEL = nukescripts.panels.registerWidgetAsPanel(
        "helper.NukePiniHelper", helper.TITLE, 'PiniHelper', create=True)
    _pane = nuke.getPaneFor('Properties.1')
    sys.PINI_HELPER_PANEL.addToPane(_pane)

    return helper.DIALOG
