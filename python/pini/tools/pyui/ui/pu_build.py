"""Tools for managing build pyui interfaces."""

from pini import dcc
from pini.utils import to_str


def build(py_file, title=None, base_col=None, load_settings=True):
    """Build interface from the given python file.

    Args:
        py_file (str): file to build from
        title (str): override interface title
        base_col (str|QColor): override interface base colour
        load_settings (bool): load settings on launch

    Returns:
        (PUBaseUi): interface instance
    """
    _path = to_str(py_file)
    if dcc.NAME == 'maya':
        from . import pu_maya
        _class = pu_maya.PUMayaUi
    else:
        raise ValueError(dcc.NAME)
    _pyui = _class(
        _path, title=title, base_col=base_col, load_settings=load_settings)
    return _pyui
