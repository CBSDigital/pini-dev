import logging
import math
import unittest

from pini import qt
from pini.qt import QtCore, QtWidgets
from pini.utils import File, assert_eq

_LOGGER = logging.getLogger(__name__)

_BLAH = False
_DIR = File(__file__).to_dir()
_UI_FILE = _DIR.to_file('settings_test.ui')
_DIALOG = None


def _set_blah_true():
    global _BLAH
    _BLAH = True


class TestQt(unittest.TestCase):

    def test_cpoint(self):

        assert qt.to_p(1) == QtCore.QPoint(1, 1)
        assert qt.to_p(1, 2) == QtCore.QPoint(1, 2)
        assert qt.to_p((1, 2)) == QtCore.QPoint(1, 2)
        assert qt.Y_AXIS == QtCore.QPoint(0, 1)

        assert isinstance(
            qt.CPoint(100, 100) / 3, (qt.CPoint, qt.CPointF))  # py2/py3
        assert isinstance(
            qt.CPoint(100, 100) / 3.0, qt.CPointF)

    def test_cpointf(self):

        # Test divide
        assert isinstance(
            qt.CPointF(100, 100) / 3, (qt.CPoint, qt.CPointF))  # py2/py3
        assert isinstance(
            qt.CPointF(100, 100) / 3.0, qt.CPointF)

        # Test add/sub
        _pt = qt.CPointF(100, 100)
        assert isinstance(_pt, qt.CPointF)
        assert isinstance(_pt + _pt, qt.CPointF)
        _pt += _pt
        assert isinstance(_pt, qt.CPointF)
        assert isinstance(_pt - _pt, qt.CPointF)
        _pt -= _pt
        assert isinstance(_pt, qt.CPointF)

    def test_cvector2d(self):

        for _angle in range(0, 361, 45):
            _rad = math.radians(_angle)
            _vec = qt.CVector2D(
                100 * math.sin(_rad),
                -100 * math.cos(_rad),
            )
            _LOGGER.info(' - %10s %30s %.02f', _angle, _vec, _vec.bearing())
            assert _angle == _vec.bearing()

    def test_list_widget(self):

        _list = qt.CListWidget()
        _list.set_items([])
        assert _list.is_empty
        assert not _list.all_items()

        # Test block signals
        global _BLAH
        _list = qt.CListWidget()
        _list.itemSelectionChanged.connect(_set_blah_true)
        _BLAH = False
        assert not _BLAH
        _list.set_items(['A', 'B', 'C'])
        assert _BLAH
        _BLAH = False
        assert not _BLAH
        _list.blockSignals(True)
        _list.set_items(['A', 'B', 'C'])
        assert not _BLAH

        # Test extended selection
        _list = qt.CListWidget()
        _list.setSelectionMode(QtWidgets.QListWidget.ExtendedSelection)
        _list.set_items(['A', 'B', 'C', 'D'])
        _list.select(['B', 'C'])
        assert _list.selected_texts() == ['B', 'C']
        _list.deleteLater()

    def test_save_settings(self):

        global _DIALOG

        class _SettingsTestUi(qt.CUiDialog):

            def __init__(self, store_settings=True):

                super().__init__(
                    ui_file=_UI_FILE.path, store_settings=store_settings)

        assert _UI_FILE.exists()
        _LOGGER.info(' - UI FILE %s', _UI_FILE)
        _DIALOG = _SettingsTestUi(store_settings=False)
        assert isinstance(_DIALOG.ui.MyTab, QtWidgets.QTabWidget)
        assert not isinstance(_DIALOG.ui.MyTab, qt.CTabWidget)
        assert _DIALOG.ui.MyTab.currentIndex() == 0
        _DIALOG.ui.MyTab.setCurrentIndex(1)
        assert _DIALOG.find_widgets()
        assert _DIALOG.ui.MyTab.currentIndex() == 1
        # _LOGGER.info(' - SAVE POLICY %s', _DIALOG.ui.MyTab.save_policy)
        _DIALOG.save_settings(force=True)
        _LOGGER.info(' - SETTINGS FILE %s', _DIALOG.settings.fileName())
        assert_eq(int(_DIALOG.settings.value('widgets/MyTab')), 1)
        _LOGGER.info(' - SETTINGS %s', _DIALOG.settings.fileName())

        _DIALOG.delete()

        _DIALOG = _SettingsTestUi(store_settings=True)
        _LOGGER.info(' - CUR TAB %s', _DIALOG.ui.MyTab.currentIndex())
        assert _DIALOG.ui.MyTab.currentIndex() == 1
        _DIALOG.delete()

    def test_to_p(self):

        _pt = qt.to_p(100, 100)
        assert isinstance(_pt, QtCore.QPoint)
        _pt = qt.to_p(100, 100, class_=qt.CPoint)
        assert isinstance(_pt, qt.CPoint)

    def test_to_size(self):

        _size = qt.to_size(0.35, class_=qt.CSizeF)
        assert _size.width() == 0.35
        assert _size.height() == 0.35
