"""General pipeline tools."""

from pini import dcc


def version_up(force=False):
    """Version up the current scene.

    Args:
        force (bool): overwrite any existing without confirmation
    """
    from pini import pipe
    from pini.tools import usage

    usage.log_usage_event('VersionUp')

    _cur_work = pipe.cur_work()
    if not _cur_work:
        dcc.error('Unable to version up - no current work file')
        return None

    _next_work = _cur_work.find_next()
    _next_work.save(force=force)

    # Update cache if not already updated (it might need to be updated
    # manually in a save callback eg. in nuke autowrite)
    if _next_work not in pipe.CACHE.cur_work_dir.works:
        pipe.CACHE.cur_work_dir.find_works(force=True)
    assert pipe.CACHE.cur_work

    # Update pini helper
    if dcc.HELPER_AVAILABLE:
        from pini.tools import helper
        if helper.is_active():
            helper.DIALOG.ui.WWorks.redraw()
            helper.DIALOG.ui.JumpToCurrent.click()

    return _next_work
