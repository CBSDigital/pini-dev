"""Tools for launching the entity select dialog."""

from pini import pipe, qt

from .es_dialog import EntitySelectUi


def launch(execute='Execute', title='Select Entity', target=None):
    """Launch the entity select dialog.

    Args:
        execute (str): label for execute button
        title (str): dialog title
        target (CPEntity): override target entity

    Returns:
        (CPEntity): selected entity
    """
    from pini.tools import entity_select, helper

    # Determine target
    _trg = target
    if not _trg and pipe.CACHE.cur_entity:
        _trg = pipe.CACHE.cur_entity
    if not _trg and helper.DIALOG and helper.DIALOG.entity:
        _trg = helper.DIALOG.entity
    if not _trg:
        _recent = pipe.CACHE.recent_entities()
        if _recent:
            _trg = _recent[0]

    # Launch dialog
    entity_select.DIALOG = EntitySelectUi(
        title=title, target=_trg, execute=execute)
    if not entity_select.DIALOG.executed:
        raise qt.DialogCancelled
    _result = entity_select.DIALOG.ui.Entity.selected_data()
    entity_select.DIALOG = None
    return _result
