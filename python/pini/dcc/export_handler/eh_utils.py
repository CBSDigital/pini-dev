"""General utilities for export handlers."""

import time

from pini import pipe, dcc
from pini.utils import get_user


def build_metadata(
        handler, action=None, work=None, sanity_check_=False, checks_data=None,
        range_=None, notes=None, task=None, source=None, content_type=None,
        force=False):
    """Obtain metadata to apply to a generated export.

    Args:
        handler (str): name of export handler
        action (str): name of action (to pass to sanity check)
        work (CPWork): override workfile to read metadata from
        sanity_check_ (bool): run sanity checks before publish
        checks_data (dict): override sanity checks data (passing this
            data will block sanity check from launching)
        range_ (tuple): override range start/end
        notes (str): export notes
        task (str): task to pass to sanity check
        source (str): path to source file
        content_type (str): apply content type data (eg. ShadersMa/VrmeshMa)
        force (bool): force completion without any confirmations

    Returns:
        (dict): metadata
    """
    from pini.tools import sanity_check, release

    _data = {}
    _data['src'] = source

    # Apply work metadata if available
    _work = work or pipe.cur_work()
    if _work:
        _data.update(_work.metadata)
        _data.pop('size', None)
        if not source:
            _data['src'] = _work.path

    _data['handler'] = handler
    _data['mtime'] = int(time.time())
    _data['owner'] = get_user()
    _data['range'] = range_ or dcc.t_range(int)
    _data['dcc'] = dcc.NAME
    _data['fps'] = dcc.get_fps()
    _data['dcc_version'] = dcc.to_version()
    _data['pini'] = release.cur_ver().to_str()
    _data['submitted'] = False
    if notes:
        _data['notes'] = notes
    if content_type:
        _data['content_type'] = content_type

    # Add sanity checks data
    if checks_data:
        _data['sanity_check'] = checks_data
    elif sanity_check_:
        _action = action or handler
        assert _action in ('render', 'publish')
        _results = sanity_check.launch_export_ui(
            action=_action, force=force, task=task)
        _data['sanity_check'] = _results

    return _data
