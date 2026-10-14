"""Parameter utilities for houdini."""

import hou

from pini.utils import to_nice


def add_parm(node, name, value, label=None, help_=None):
    """Add parmeter to the given node.

    Args:
        node (Node): node to add parameter to
        name (str): parameter name
        value (any): parameter value
        label (str): parameter label
        help_ (str): help/tooltip for parameter

    Returns:
        (Parm): parameter
    """
    _parm = node.parm(name)
    if _parm:
        raise NotImplementedError('Type check existing')

    _label = label or to_nice(name)
    if isinstance(value, bool):
        _ptg = node.parmTemplateGroup()
        tmpl = hou.ToggleParmTemplate(
            name, _label, default_value=value, help=help_)
        _ptg.append(tmpl)
        node.setParmTemplateGroup(_ptg)
        _parm = node.parm(name)

    else:
        raise NotImplementedError(value)

    return _parm
