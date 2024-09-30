"""Tools for managing build pyui interfaces."""

from pini import dcc, qt
from pini.utils import to_str


def build(py_file, title=None, base_col=None, load_settings=True, mode=None):
    """Build interface from the given python file.

    Args:
        py_file (str): file to build from
        title (str): override interface title
        base_col (str|QColor): override interface base colour
        load_settings (bool): load settings on launch
        mode (str): override default ui mode (eg. maya/qt)

    Returns:
        (PUBaseUi): interface instance
    """
    _path = to_str(py_file)

    # Determine mode
    _mode = mode
    if _mode is None:
        _mode = 'maya' if dcc.NAME == 'maya' else 'qt'

    # Obtain ui class
    if _mode == 'maya':
        from . import pu_maya
        _class = pu_maya.PUMayaUi
    elif _mode == 'qt':
        from . import pu_qt
        if not dcc.NAME:
            qt.set_dark_style(mode='qdarkstyle')
        _class = pu_qt.PUQtUi
    else:
        raise ValueError(_mode)

    # Build interface
    _pyui = _class(
        _path, title=title, base_col=base_col, load_settings=load_settings)
    return _pyui
