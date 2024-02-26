"""Install pini tools to current dcc."""

import logging
import os

from pini import dcc, testing

_LOGGER = logging.getLogger(__name__)


def setup(build_ui=True, setup_logging=False):
    """Setup pini tools.

    Args:
        build_ui (bool): build ui elements
        setup_logging (bool): set up logging with a basic handler

    Returns:
        (bool): whether pini was installed successfully
    """
    from pini import install

    # Test for disable
    if os.environ.get('PINI_INSTALL_DISABLE'):
        _LOGGER.info(" - SETUP DISABLED VIA $PINI_INSTALL_DISABLE")
        return True

    _LOGGER.debug('SETUP PINI %s', dcc.NAME)

    if setup_logging:
        testing.setup_logging()

    # Build ui
    if _build_ui_disabled(build_ui=build_ui):
        return True
    if install.INSTALLER:
        _LOGGER.info(' - EXECUTING INSTALLER %s', install.INSTALLER)
        install.INSTALLER.run()
        return True

    raise RuntimeError('No installer found')


def _build_ui_disabled(build_ui):
    """Test whether build ui elements is disabled.

    Args:
        build_ui (bool): build ui flag setting

    Returns:
        (bool): whether ui elements should be built
    """

    if not build_ui:
        return True

    if dcc.batch_mode():
        _LOGGER.info(' - BATCH MODE - NOT BUILDING UI ELEMENTS')
        return True

    if os.environ.get('PINI_UI INSTALL_DISABLE'):
        _LOGGER.info(" - BUILD UI DISABLED VIA $PINI_INSTALL_UI_DISABLE")
        return True

    return False
