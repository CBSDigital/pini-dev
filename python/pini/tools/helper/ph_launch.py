"""Tools for managing launching pini helper."""

import copy
import logging

from pini import dcc
from pini.tools import error, usage

from . import ph_dialog

_LOGGER = logging.getLogger(__name__)


@usage.get_tracker('LaunchPiniHelper')
@error.catch
def launch(jump_to=None, admin=None, parent=None, load_settings=True, show=True,  # pylint: disable=unused-argument
           use_basic=False):
    """Launch PiniHelper interface.

    Args:
        jump_to (str): jump interface to path
        admin (bool): launch in admin mode with create entity/task options
        parent (QDialog): parent dialog
        load_settings (bool): load settings on launch
        show (bool): show on launch
        use_basic (bool): ignore any dcc overrides

    Returns:
        (PiniHelper): PiniHelper instance
    """
    _LOGGER.debug('LAUNCH')
    _kwargs = copy.copy(locals())
    _kwargs.pop('use_basic')
    _LOGGER.debug(' - KWARGS (A) %s', _kwargs)
    from pini.tools import helper

    # Determine class
    _class = ph_dialog.PiniHelper
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

    # Build ui
    _LOGGER.debug(' - KWARGS (B) %s', _kwargs)
    _dialog = _class(**_kwargs)

    return helper.DIALOG
