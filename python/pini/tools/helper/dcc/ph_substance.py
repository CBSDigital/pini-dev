"""Tools for managing the substance pini helper."""

# pylint: disable=abstract-method,too-many-ancestors

import logging

from .. import ph_dialog

_LOGGER = logging.getLogger(__name__)


class SubstancePiniHelper(ph_dialog.PiniHelper):
    """Pini helper dialog for substance."""
