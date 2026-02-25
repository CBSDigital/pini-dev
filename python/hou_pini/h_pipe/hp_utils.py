"""General houdini pipeline utilities."""

from pini.utils import get_user


def to_output_path_expr(template='render', extn='exr'):
    """Build a python expression to obtain an output path.

    Args:
        template (str): template name
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
