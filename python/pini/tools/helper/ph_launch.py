"""Tools for managing launching pini helper."""

# pylint: disable=unused-argument

import copy
import logging

from pini import dcc
from pini.tools import error, usage

from . import ph_window

_LOGGER = logging.getLogger(__name__)


@usage.get_tracker('LaunchPiniHelper')
@error.catch
def launch(
        jump_to=None, admin=None, parent=None, store_settings=True, show=True,
        use_basic=False, reset_cache=True, title=None):
    """Launch PiniHelper interface.

    Args:
        jump_to (str): jump interface to path
        admin (bool): launch in admin mode with create entity/task options
        parent (QDialog): parent dialog
        store_settings (bool): load settings on launch
        show (bool): show on launch
        use_basic (bool): ignore any dcc overrides
        reset_cache (bool): reset pipeline cache on launch
        title (str): override helper window title

    Returns:
        (PiniHelper): PiniHelper instance
    """
    _LOGGER.debug('LAUNCH')
    _kwargs = copy.copy(locals())
    _kwargs.pop('use_basic')
    _LOGGER.debug(' - KWARGS (A) %s', _kwargs)
    from pini.tools import helper

    # Determine class
    _class = ph_window.PiniHelper
    if use_basic:
        pass
    elif dcc.NAME == 'maya':
        from .dcc import ph_maya
        _class = ph_maya.MayaPiniHelper
    elif dcc.NAME == 'nuke':
        from .dcc import ph_nuke
        return ph_nuke.launch()
    elif dcc.NAME == 'hou':
        from .dcc import ph_hou
        _class = ph_hou.HouPiniHelper
    elif dcc.NAME == 'substance':
        from .dcc import ph_substance
        _class = ph_substance.SubstancePiniHelper

    # Build ui
    _LOGGER.debug(' - KWARGS (B) %s', _kwargs)
    _dialog = _class(**_kwargs)

    return helper.DIALOG
