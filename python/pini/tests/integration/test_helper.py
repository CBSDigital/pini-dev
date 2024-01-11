import unittest
import logging

from pini import testing, dcc, pipe
from pini.tools import helper, error
from pini.utils import File, assert_eq

_LOGGER = logging.getLogger(__name__)


class TestHelper(unittest.TestCase):

    def setUp(self):
        assert not error.TRIGGERED
        if not helper.DIALOG:
            helper.launch()
        assert not error.TRIGGERED

    def test_helper_caching(self):

        assert not error.TRIGGERED

        dcc.new_scene(force=True)

        # Check outputs exists
        _work = testing.TEST_SHOT.to_work(task='anim', tag='test')
        if not testing.TEST_SHOT.find_outputs('cache'):
            _abc = _work.to_output(
                'cache', output_type='char', output_name='null', extn='abc')
            _abc.touch()
            assert testing.TEST_SHOT.find_outputs('cache')
        if not testing.TEST_SHOT.find_outputs('render'):
            _render = _work.to_output(
                'render', output_name='null', extn='jpg')
            for _frame in range(1001, 1006):
                File(_render[_frame]).touch()
            assert testing.TEST_SHOT.find_outputs('render')

        # Check switch helper output tabs with file system disabled
        _helper = helper.DIALOG
        _helper.jump_to(testing.TEST_SHOT)
        for _en in (True, False):
            testing.enable_file_system(_en)
            _helper.ui.MainPane.select_tab('Scene')
            if dcc.NAME == 'maya':
                _types = ['Asset', 'Cache', 'Render']
            elif dcc.NAME in ('nuke', 'hou'):
                _types = ['Cache', 'Render']
            else:
                raise NotImplementedError(dcc.NAME)
            for _type in _types:
                _helper.ui.SOutputsPane.select_tab(_type)
                assert _helper.ui.SOutputs.all_data()
            _helper.ui.MainPane.select_tab('Export')
        testing.enable_file_system(True)
        _helper.ui.MainPane.select_tab('Scene')

        assert not error.TRIGGERED

    def test_save_new_tag(self):

        _LOGGER.info('TEST SAVE NEW TAG')

        assert not error.TRIGGERED

        _shot = testing.TEST_SHOT
        _shot_c = pipe.CACHE.obt(testing.TEST_SHOT)
        _work_dir_c = _shot_c.find_work_dir(task='anim', dcc_=dcc.NAME)
        _work = _work_dir_c.to_work()
        _LOGGER.info(' - WORK %s', _work.path)

        # Reset
        for _o_work in _work.work_dir.find_works():
            if _o_work.tag and 'tmp' not in _o_work.tag:
                continue
            _o_work.delete(force=True)
        dcc.new_scene(force=True)
        _work.save(force=True)

        pipe.CACHE.reset()
        assert pipe.CACHE.cur_entity
        assert pipe.CACHE.cur_work_dir
        assert pipe.cur_work()
        assert pipe.CACHE.cur_work

        _helper = helper.DIALOG
        if not _helper:
            _helper = helper.launch()
        else:
            _helper.ui.Refresh.click()
        _helper.jump_to(_work)
        assert_eq(_helper.work, _work)
        _helper.ui.WWorksRefresh.click()
        assert_eq(_helper.work, pipe.CACHE.cur_work)

        _work_dir_c = _helper.work_dir
        assert _helper.job is pipe.CACHE.cur_job
        assert _helper.work_dir is pipe.CACHE.cur_work_dir
        assert _helper.work is pipe.CACHE.cur_work

        _helper.ui.WTagText.setText('tmp1')
        assert _helper.work_dir is pipe.CACHE.cur_work_dir
        assert _helper.work_dir is _work_dir_c

        assert _helper.work
        _helper._callback__WSave(force=True)
        assert _helper.work_dir is pipe.CACHE.cur_work_dir
        assert _helper.work is pipe.CACHE.cur_work

        assert not error.TRIGGERED

    def scene_refs_filter_test(self):

        assert not error.TRIGGERED

        _filters = [helper.DIALOG.ui.SSceneRefsShowLookdevs,
                    helper.DIALOG.ui.SSceneRefsShowRigs,
                    helper.DIALOG.ui.SSceneRefsShowAbcs]
        helper.DIALOG.ui.SSceneRefsTypeFilterReset.click()
        for _filter in _filters:
            assert not _filter.isChecked()
        helper.DIALOG.ui.SSceneRefsShowRigs.setChecked(True)
        helper.DIALOG.ui.SSceneRefsTypeFilterReset.click()
        for _filter in _filters:
            assert not _filter.isChecked()

        assert not error.TRIGGERED
