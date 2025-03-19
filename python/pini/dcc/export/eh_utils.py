"""General utilities for export handlers."""

import time

from pini import pipe, dcc, qt
from pini.utils import get_user, to_str


def build_metadata(
        handler, action=None, work=None, sanity_check_=False, checks_data=None,
        range_=None, notes=None, task=None, src=None, bkp=None,
        content_type=None, src_ref=None, require_notes=False, force=False):
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
        src (str): path to source file
        bkp (str): path to bkp file for this export (ie. timestamped copy
            of scene file)
        content_type (str): apply content type data (eg. ShadersMa/VrmeshMa)
        src_ref (str): path to source reference (eg. rig path)
        require_notes (bool): request notes if none are provided
        force (bool): force completion without any confirmations

    Returns:
        (dict): metadata
    """
    from pini.tools import sanity_check, release

    _data = {}
    _data['handler'] = handler
    if src:
        _data['src'] = to_str(src)
    if bkp:
        _data['bkp'] = to_str(bkp)
    if src_ref:
        _data['src_ref'] = src_ref

    # Apply work metadata if available
    _work = work or pipe.cur_work()
    if _work:
        _data.update(_work.metadata)
        _data.pop('size', None)
        if not src:
            _data['src'] = _work.path

    _data['mtime'] = int(time.time())
    _data['owner'] = get_user()
    _data['range'] = range_ or dcc.t_range(int)
    _data['dcc'] = dcc.NAME
    _data['fps'] = dcc.get_fps()
    _data['dcc_version'] = dcc.to_version()
    _data['pini'] = release.cur_ver().to_str()
    _data['submitted'] = False
    if content_type:
        _data['content_type'] = content_type

    # Apply notes
    _notes = notes
    if not _notes and require_notes and not force:
        _notes = qt.input_dialog(
            'Please enter notes for this export:', title='Notes')
    if _notes:
        _data['notes'] = _notes

    # Add sanity checks data
    if checks_data:
        _data['sanity_check'] = checks_data
    elif sanity_check_:
        _action = action or handler
        _results = sanity_check.launch_export_ui(
            action=_action, force=force, task=task)
        _data['sanity_check'] = _results

    return _data
