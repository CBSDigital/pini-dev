"""General houdini pipeline utilities."""

import hou

from pini import pipe
from pini.utils import get_user, apply_deprecation


def to_output_path_expr(template='render', extn='exr', aov=True):
    """Build a python expression to obtain an output path.

    Args:
        template (str): output template name
        extn (str): output file extension
        aov (bool): include AOV token (to match maya cryptomatte naming)

    Returns:
        (str): python expression
    """
    apply_deprecation('02/10/26', 'Use to_output_path')
    _user = get_user()
    if aov:
        _f_expr = '_$AOV.$F4.'
    else:
        _f_expr = '.$F4.'
    return '\n'.join([
        "from pini import pipe",
        "_work = pipe.cur_work()",
        "_output_name = hou.pwd().name()",
        "_out = _work.to_output(",
        f"    '{template}', extn='{extn}', output_name=_output_name)",
        f"return _out.path.replace('.%04d.', '{_f_expr}')"])


def to_output_path(
        template='render', extn='exr', output_name=None, apply_frame=True,
        aov=True):
    """Build an output path.

    Args:
        template (str): output template name
        extn (str): output file extension
        output_name (str): override output name (default is current node name)
        apply_frame (bool): apply frame number (otherwise use $F4 expr)
        aov (bool): include AOV token (to match maya cryptomatte naming)

    Returns:
        (str): path to output
    """
    _work = pipe.cur_work()
    _output_name = output_name or hou.pwd().name()
    if not _output_name:
        raise ValueError('Missing output name')
    _out = _work.to_output(template, extn=extn, output_name=_output_name)
    if aov:
        _f_expr = '.$AOV.$F4.'
    else:
        _f_expr = '.$F4.'
    _path = _out.path.replace('.%04d.', _f_expr)
    if apply_frame:
        return _path.replace('.$F4.', f'.{hou.intFrame():04d}.')
    return _path
