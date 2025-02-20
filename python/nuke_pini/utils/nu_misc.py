"""General selection utilities for nuke."""

import nuke


def clear_selection():
    """Deselect all nodes."""
    for _node in nuke.allNodes():
        _node.setSelected(False)


def set_node_col(node, col):
    """Set node graph colour of the given node.

    Args:
        node (str|Node): node to update
        col (str): colour to apply (eg. DodgerBlue)
    """
    from pini import qt
    _node = node
    if isinstance(_node, str):
        _node = nuke.toNode(_node)

    _name = qt.CColor(col).name().strip('#') + 'ff'
    _val = int(_name, 16)
    _node['tile_color'].setValue(_val)
