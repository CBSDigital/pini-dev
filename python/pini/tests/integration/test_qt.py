import unittest

from pini import qt, dcc
from pini.tools import release


class TestQt(unittest.TestCase):

    def test_progress_bar_unhiding(self):

        qt.close_all_progress_bars(filter_='Test')

        _top = qt.progress_dialog(stack_key='TestTop')
        _mid = qt.progress_dialog(stack_key='TestMid')
        assert _mid.pos().y() > _top.pos().y()
        _bot = qt.progress_dialog(stack_key='TestBot')
        assert _bot.pos().y() > _top.pos().y()
        assert _bot.pos().y() > _mid.pos().y()

        qt.close_all_progress_bars(filter_='Test')

        _top = qt.progress_dialog(stack_key='TestTop')
        _mid = qt.progress_dialog(stack_key='TestMid', show_delay=1)
        assert _mid.pos().y() > _top.pos().y()
        assert not _mid.isVisible()
        _bot = qt.progress_dialog(stack_key='TestBot')
        assert _bot.pos().y() > _top.pos().y()
        assert _bot.pos().y() > _mid.pos().y()
        assert _mid.isVisible()

        qt.close_all_progress_bars(filter_='Test')

        _top = qt.progress_dialog(stack_key='TestTop')
        _mid = qt.progress_dialog(stack_key='TestMid', show_delay=1)
        assert _mid.pos().y() > _top.pos().y()
        assert not _mid.isVisible()
        _bot = qt.progress_dialog(stack_key='TestBot', show_delay=1)
        assert _bot.pos().y() > _top.pos().y()
        assert _bot.pos().y() > _mid.pos().y()
        assert not _mid.isVisible()
        assert not _bot.isVisible()

        qt.close_all_progress_bars(filter_='Test')

        _top = qt.progress_dialog(stack_key='TestTop')
        _mid = qt.progress_dialog(stack_key='TestMid', show_delay=1)
        assert _mid.pos().y() > _top.pos().y()
        assert not _mid.isVisible()
        _bot = qt.progress_dialog(stack_key='TestBot', show_delay=1)
        assert _bot.pos().y() > _top.pos().y()
        assert _bot.pos().y() > _mid.pos().y()
        assert not _mid.isVisible()
        assert not _bot.isVisible()
        _bot.show()
        assert _mid.isVisible()
        assert _bot.isVisible()
        _bot.set_pc(100)
        assert _mid.isVisible()
        assert not _bot.isVisible()
        _bot = qt.progress_dialog(stack_key='TestBot', show_delay=1)
        _bot.show()
        assert _bot.pos().y() > _mid.pos().y()

        qt.close_all_progress_bars(filter_='Test')

    def test_block_load_offscreen_geometry(self):

        _ui_file = release.PINI.to_file('python/pini/tests/unit/settings_test.ui')
        assert _ui_file.exists()
        _ui = qt.CUiDialog(ui_file=_ui_file)

        # Make sure ui onscreen + settings load
        _main = dcc.get_main_window_ptr()
        _on_pos = _main.pos() + qt.to_p(100)
        assert qt.p_is_onscreen(_on_pos)
        _ui.move(_on_pos)
        _ui.resize(1000, 700)
        _ui.save_settings()
        print()
        assert _ui._load_geometry_settings(screen='N/A')

        # Check load geometry rejected of offscreen
        _off_pos = _main.pos() - qt.to_p(200)
        assert not qt.p_is_onscreen(_off_pos)
        _ui.move(_off_pos)
        _ui.save_settings()
        assert not _ui._load_geometry_settings(screen='N/A')
        _ui.delete()
