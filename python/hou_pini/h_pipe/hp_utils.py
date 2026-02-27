"""General houdini pipeline utilities."""

import hou

from pini import pipe
from pini.utils import get_user


def to_output_path_expr(template='render', extn='exr'):
    """Build a python expression to obtain an output path.

    Args:
        template (str): output template name
        extn (str): output file extension

    Returns:
        (str): python expression
    """
    _user = get_user()
    return '\n'.join([
        # "import pini_startup",
        # f"pini_startup.init(setup_logging=False, user='{_user}')",
        "from pini import pipe",
        "_work = pipe.cur_work()",
        "_output_name = hou.pwd().name()",
        "_out = _work.to_output(",
        f"    '{template}', extn='{extn}', output_name=_output_name)",
        "return _out.path.replace('.%04d.', '.$F4.')"])


def to_output_path(
        template='render', extn='exr', output_name=None, apply_frame=True):
    """Build an output path.

    Args:
        template (str): output template name
        extn (str): output file extension
        output_name (str): override output name (default is current node name)
        apply_frame (bool): apply frame number (otherwise use $F4 expr)

    Returns:
        (str): path to output
    """
    _work = pipe.cur_work()
    _output_name = output_name or hou.pwd().name()
    if not _output_name:
        raise ValueError('Missing output name')
    _out = _work.to_output(template, extn=extn, output_name=_output_name)
    if apply_frame:
        return _out[hou.intFrame()]
    return _out.path.replace('.%04d.', '.$F4.')
