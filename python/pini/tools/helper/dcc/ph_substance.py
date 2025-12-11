"""Tools for managing the substance pini helper."""

# pylint: disable=abstract-method,too-many-ancestors

import logging

from .. import ph_window

_LOGGER = logging.getLogger(__name__)


class SubstancePiniHelper(ph_window.PiniHelper):
    """Pini helper dialog for substance."""
