import unittest
import logging

from pini import testing, dcc, pipe
from pini.tools import helper
from pini.utils import File

_LOGGER = logging.getLogger(__name__)


class TestHelper(unittest.TestCase):

    def setUp(self):
        if not helper.DIALOG:
            helper.launch()

    def test_helper_caching(self):

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

    def test_save_new_tag(self):

        _shot = testing.TEST_SHOT
        _work = _shot.to_work(task='anim')

        # Reset
        for _o_work in _work.work_dir.find_works():
            if _o_work.tag and 'tmp' not in _o_work.tag:
                continue
            _o_work.delete(force=True)
        dcc.new_scene(force=True)
        _work.save(force=True)
        pipe.CACHE.reset()

        _cl = helper.DIALOG
        if not _cl:
            _cl = helper.launch()
        else:
            _cl.ui.Refresh.click()
        _cl.jump_to(_work.path)
        _cl.ui.WWorksRefresh.click()

        _work_dir_c = _cl.work_dir
        assert _cl.job is pipe.CACHE.cur_job
        assert _cl.work_dir is pipe.CACHE.cur_work_dir
        assert _cl.work is pipe.CACHE.cur_work

        _cl.ui.WTagText.setText('tmp1')
        assert _cl.work_dir is pipe.CACHE.cur_work_dir
        assert _cl.work_dir is _work_dir_c

        _cl._callback__WSave(force=True)
        assert _cl.work_dir is pipe.CACHE.cur_work_dir
        assert _cl.work is pipe.CACHE.cur_work

    def scene_refs_filter_test(self):

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
