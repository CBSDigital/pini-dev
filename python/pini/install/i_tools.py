"""Install pini tools to current dcc."""

import logging
import os
import sys

from pini import dcc, pipe, testing

_LOGGER = logging.getLogger(__name__)


def setup(build_ui=True, install_mod=None, set_work_callback=None,
          create_asset_type_callback=None, create_asset_callback=None,
          create_sequence_callback=None, create_shot_callback=None,
          setup_logging=False):
    """Setup pini tools.

    Args:
        build_ui (bool): build ui elements
        install_mod (mod): override setup module - this should have the
            same install.setup function
        set_work_callback (fn): callback to execute on update current work
        create_asset_type_callback (fn): callback to execute on create
            asset type
        create_asset_callback (fn): callback to execute on create asset
        create_sequence_callback (fn): callback to execute on create sequence
        create_shot_callback (fn): callback to execute on create shot
        setup_logging (bool): set up logging with a basic handler

    Returns:
        (bool): whether pini was installed successfully
    """
    from pini import install

    # Test for disable
    if os.environ.get('PINI_INSTALL_DISABLE'):
        _LOGGER.info(" - SETUP DISABLED VIA $PINI_INSTALL_DISABLE")
        return True

    _LOGGER.debug('SETUP PINI %s install_mod=%s', dcc.NAME, install_mod)

    if setup_logging:
        testing.setup_logging()

    # Set install module, so setup can be reapplied on refresh - this allows
    # elements to be reinstalled (eg. render_handlers)
    if install_mod:
        sys.PINI_INSTALL_MOD = install_mod
    if not hasattr(sys, 'PINI_INSTALL_MOD'):
        sys.PINI_INSTALL_MOD = install
    _LOGGER.debug(' - SET sys.PINI_INSTALL_MOD %s', sys.PINI_INSTALL_MOD)

    # Apply callbacks
    if set_work_callback:
        pipe.apply_set_work_callback(set_work_callback)
    if create_asset_type_callback:
        pipe.apply_create_asset_type_callback(create_asset_type_callback)
    if create_asset_callback:
        pipe.apply_create_asset_callback(create_asset_callback)
    if create_sequence_callback:
        pipe.apply_create_sequence_callback(create_sequence_callback)
    if create_shot_callback:
        pipe.apply_create_shot_callback(create_shot_callback)

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
