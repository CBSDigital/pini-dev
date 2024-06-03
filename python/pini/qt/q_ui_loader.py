"""Tools for managing the custom ui file loader."""


def build_ui_loader():
    """Build pini.qt ui loader.

    Returns:
        (QUiLoader): ui loader
    """
    from pini import qt
    from .q_mgr import QtUiTools

    _loader = QtUiTools.QUiLoader()
    _loader.registerCustomWidget(qt.CComboBox)
    _loader.registerCustomWidget(qt.CGraphSpace)
    _loader.registerCustomWidget(qt.CLabel)
    _loader.registerCustomWidget(qt.CPixmapLabel)
    _loader.registerCustomWidget(qt.CLineEdit)
    _loader.registerCustomWidget(qt.CListView)
    _loader.registerCustomWidget(qt.CListWidget)
    _loader.registerCustomWidget(qt.CSlider)
    _loader.registerCustomWidget(qt.CSplitter)
    _loader.registerCustomWidget(qt.CTabWidget)
    _loader.registerCustomWidget(qt.CTileWidget)
    _loader.registerCustomWidget(qt.CTreeWidget)

    return _loader
