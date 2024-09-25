import unittest

from pini import qt


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
