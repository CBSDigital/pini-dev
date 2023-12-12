"""Tools for managing layouts.

Annoyingly these can't be overridden in designer, so instead these helper
functions are used to manage them.
"""


def delete_layout(layout):
    """Delete the given layout and all its contents.

    Args:
        layout (QLayout): layout to delete
    """
    flush_layout(layout)
    layout.deleteLater()


def flush_layout(layout):
    """Flush contents of the given layout.

    Args:
        layout (QLayout): layout to clean
    """
    while layout.count():
        _item = layout.itemAt(0)
        if _item.widget():
            _item.widget().deleteLater()
        if _item.layout():
            delete_layout(_item.layout())
        layout.removeItem(_item)


def find_layout_widgets(layout):
    """Find widgets in the given layout.

    Args:
        layout (QLayout): layout to search

    Returns:
        (QWidget list): widgets
    """
    _widgets = []
    for _idx in range(layout.count()):
        _item = layout.itemAt(_idx)
        _widget = _item.widget()
        if _widget:
            _widgets.append(_widget)
        _lyt = _item.layout()
        if _lyt:
            _widgets += find_layout_widgets(_lyt)
    return _widgets
