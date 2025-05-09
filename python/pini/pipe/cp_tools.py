"""General pipeline tools."""

from pini import dcc
from pini.tools import error


@error.catch
def version_up(parent=None, force=False):
    """Version up the current scene.

    Args:
        parent (QWidget): parent dialog
        force (bool): overwrite any existing without confirmation

    Returns:
        (CCPWork): new work file
    """
    from pini import pipe
    from pini.tools import usage

    usage.log_usage_event('VersionUp')

    _cur_work = pipe.cur_work()
    if not _cur_work:
        _cur_file = dcc.cur_file()
        if _cur_file:
            _msg = (
                f'Unable to version up - current scene is not a '
                f'work file.\n\n{_cur_file}')
        else:
            _msg = 'Unable to version up.\n\nNo current scene.'
        raise error.HandledError(_msg, parent=parent)

    _next_work = _cur_work.find_next()
    _next_work.save(parent=parent, force=force)

    # Update cache if not already updated (it might need to be updated
    # manually in a save callback eg. in nuke autowrite)
    _next_work = pipe.CACHE.obt_cur_work()
    assert _next_work

    # Update pini helper
    if dcc.HELPER_AVAILABLE:
        from pini.tools import helper
        if helper.is_active():
            helper.DIALOG.ui.WWorks.redraw()
            helper.DIALOG.ui.JumpToCurrent.click()

    return _next_work
