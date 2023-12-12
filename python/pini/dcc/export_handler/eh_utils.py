"""General utilities for export handlers."""

import copy
import time

from pini import pipe, dcc
from pini.utils import get_user


def obtain_metadata(
        handler, action=None, work=None, sanity_check_=False,
        force=False, notes=None):
    """Obtain metadata to apply to a generated export.

    Args:
        handler (str): name of export handler
        action (str): name of action (to pass to sanity check)
        work (CPWork): override workfile to read metadata from
        sanity_check_ (bool): run sanity checks before publish
        force (bool): force completion without any confirmations
        notes (str): export notes

    Returns:
        (dict): metadata
    """
    from pini.tools import sanity_check, release

    _work = work or pipe.cur_work()
    _data = copy.copy(_work.metadata)
    _data.pop('size', None)

    _data['handler'] = handler
    _data['mtime'] = int(time.time())
    _data['owner'] = get_user()
    _data['range'] = dcc.t_range(int)
    _data['src'] = _work.path
    _data['dcc'] = dcc.NAME
    _data['dcc_version'] = dcc.to_version()
    _data['pini'] = release.cur_ver().to_str()
    _data['submitted'] = False
    if notes:
        _data['notes'] = notes

    if sanity_check_:
        _action = action or handler
        assert _action in ('render', 'publish')
        _results = sanity_check.launch_export_ui(
            mode=_action, force=force)
        _data['sanity_check'] = _results

    return _data
