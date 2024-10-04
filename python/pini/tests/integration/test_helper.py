import unittest
import logging

from pini import testing, dcc, pipe, qt
from pini.tools import helper, error
from pini.utils import File, assert_eq, system, strftime

_LOGGER = logging.getLogger(__name__)


class TestHelper(unittest.TestCase):

    # def setUp(self):
    #     assert not error.TRIGGERED
    #     if not helper.is_active():
    #         helper.launch(reset_cache=False)
    #     assert not error.TRIGGERED

    def test_for_cyclical_import(self):

        # NOTE: doesn't seem to give output for some reason (could pipe out
        # to file if wanted)
        _cmd = 'print("HELLO"); from pini.tools import helper; print(helper)'
        _out, _err = system(
            ['python', '-c', '"""{}"""'.format(_cmd)], result='out/err')
        print(_out)
        print(_err)
        assert not _err

    def test_helper_caching(self):

        dcc.new_scene(force=True)

        # Check outputs exists
        _work = testing.TEST_SHOT.to_work(task='anim', tag='test')
        _shot_c = pipe.CACHE.obt(testing.TEST_SHOT)
        if not _shot_c.find_outputs('cache'):
            _abc = _work.to_output(
                'cache', output_type='char', output_name='null', extn='abc')
            _abc.touch()
            assert _shot_c.find_outputs('cache')
        if not _shot_c.find_outputs('render'):
            _render = _work.to_output(
                'render', output_name='null', extn='jpg')
            for _frame in range(1001, 1006):
                File(_render[_frame]).touch()
            assert testing.TEST_SHOT.find_outputs('render')

        assert not error.TRIGGERED

        # Check switch helper output tabs with file system disabled
        print()
        _LOGGER.info('CHECK SWITCH OUTPUT TABS')
        _helper = helper.obt_helper()
        _helper.jump_to(testing.TEST_SHOT)
        for _en in (True, False):

            print()
            _LOGGER.info(' - APPLYING SCENE TAB %s', _helper.job)
            testing.enable_file_system(_en)

            _helper.ui.MainPane.select_tab('Scene')
            if dcc.NAME == 'maya':
                _types = ['Asset', 'Cache', 'Render']
            elif dcc.NAME in ('nuke', 'hou'):
                _types = ['Cache', 'Render']
            else:
                raise NotImplementedError(dcc.NAME)
            _LOGGER.info(' - CHECKING TYPES %s', _types)

            for _type in _types:
                _LOGGER.info(' - CHECKING TYPE %s %s', _type, _helper.entity)
                _helper.ui.SOutputsPane.select_tab(_type)
                _helper.ui.SOutputVers.select_text('latest')
                assert _helper.ui.SOutputs.all_data()
                assert _helper.ui.SOutputsPane.current_tab_text() == _type
                _outs = _helper.ui.SOutputs.all_data()
                _LOGGER.info('   - TASK %s', _helper.ui.SOutputTask.currentText())
                _LOGGER.info('   - TAG %s', _helper.ui.SOutputTag.currentText())
                _LOGGER.info('   - VERS %s', _helper.ui.SOutputVers.currentText())
                _LOGGER.info('   - DISPLAYING %d OUTS %s', len(_outs), _outs)

            _LOGGER.info(' - REVERTING TO EXPORT TAB')
            _helper.ui.MainPane.select_tab('Export')

            assert not error.TRIGGERED

        testing.enable_file_system(True)
        _helper.ui.MainPane.select_tab('Scene')

    def test_save_new_tag(self):

        _LOGGER.info('TEST SAVE NEW TAG')

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

    def test_scene_refs_filter(self):

        _helper = helper.obt_helper()

        _filters = [_helper.ui.SSceneRefsShowLookdevs,
                    _helper.ui.SSceneRefsShowRigs,
                    _helper.ui.SSceneRefsShowAbcs]
        _helper.ui.SSceneRefsTypeFilterReset.click()
        for _filter in _filters:
            assert not _filter.isChecked()
        _helper.ui.SSceneRefsShowRigs.setChecked(True)
        _helper.ui.SSceneRefsTypeFilterReset.click()
        for _filter in _filters:
            assert not _filter.isChecked()

    def test_store_settings_in_scene_basic(self):

        _LOGGER.info('STORE SETTINGS IN SCENE TEST')

        _ety_c = pipe.CACHE.obt(testing.TEST_SHOT)
        _work_dir = _ety_c.find_work_dir(dcc_=dcc.NAME, task='anim')
        _LOGGER.info(' - WORK DIR %s', _work_dir)
        _work = _work_dir.to_work()
        _LOGGER.info(' - WORK %s', _work)

        _helper = helper.DIALOG
        _helper.jump_to(_work)
        dcc.new_scene(force=True)
        _work.save(force=True)

        # Select tab to store data in scene
        _helper.ui.MainPane.select_tab('Export')
        _tab = _helper.ui.EExportPane.find_tabs(enabled=True)[-1]
        _LOGGER.info(' - TAB %s', _tab)
        assert _helper.ui.EExportPane.save_policy == qt.SavePolicy.SAVE_IN_SCENE
        _LOGGER.info(' - SCENE SETTINGS KEY %s', _helper.ui.EExportPane.settings_key)
        _helper.ui.EExportPane.select_tab(_tab, emit=True)
        assert _helper.ui.EExportPane.current_tab_text() == _tab
        assert dcc.get_scene_data('PiniQt.ExportTab.EExportPane')
        assert dcc.get_scene_data('PiniQt.ExportTab.EExportPane') == _tab

        # Re-open helper and check render tab is still selected
        _helper.close()
        _helper = helper.launch(reset_cache=False)
        _helper.ui.MainPane.select_tab('Export')
        assert _helper.ui.EExportPane.current_tab_text() == _tab


class TestDiskPiniHelper(TestHelper):

    pipe_master_filter = 'disk'

    def test_pini_helper_create(self):

        assert not error.TRIGGERED

        dcc.new_scene(force=True)
        _helper = helper.obt_helper(reset_cache=False)
        _helper._callback__ToggleAdmin(True)

        _job = testing.TEST_JOB
        _seq_name = strftime('Tmp_%y%m%d_%H%M%S')

        # Test create seq
        _shot = _job.find_shots()[0]
        assert _shot.exists()
        _LOGGER.info('JUMP TO %s', _shot)
        _helper.jump_to(_shot.path)
        assert not _helper.ui.EntityTypeCreate.isEnabled()
        _helper.ui.EntityType.setEditText(_seq_name)
        assert _helper.ui.EntityTypeCreate.isEnabled()
        assert not _helper.ui.EntityCreate.isEnabled()
        _helper.ui.Entity.setEditText('shot010')
        assert _helper.ui.EntityCreate.isEnabled()
        _helper._callback__EntityCreate(force=True, shotgrid_=False)
        _seq = _helper.ui.EntityType.selected_data()
        assert _seq
        assert _seq.name == _seq_name
        assert _helper.entity.exists()
        _helper.entity.set_setting(shotgrid={'disable': True})
        assert _helper.entity.settings['shotgrid']['disable']

        # Test save/load
        _work = _helper.work
        _LOGGER.info(' - WORK (A) %s', _work)
        _LOGGER.info(' - SEQ NAME %s', _seq_name)
        _LOGGER.info(' - WORK DIR %s', _helper.work_dir)
        _LOGGER.info(' - WORK (B) %s', _helper.work)
        assert _work.sequence == _seq_name
        assert len(_helper.ui.WWorks.all_data()) == 1
        _helper._callback__WSave(force=True)
        assert pipe.cur_work() == _work
        _works = _helper.ui.WWorks.all_data()
        assert len(_works) == 2
        _helper.ui.WWorks.select_data(_works[0])
        assert _helper.ui.WWorks.selected_data().ver_n == 2
        _helper._callback__WSave(force=True)
        assert pipe.cur_work().ver_n == 2
        assert _work.ver_n == 1
        _helper.ui.WWorks.select_data(_work)
        _helper._callback__WLoad(force=True)
        assert pipe.cur_work().ver_n == 1

        # Test create new task
        _tasks = _helper.ui.WTasks.all_text()
        _task = 'groom'
        assert _task not in _tasks
        _helper.ui.WTaskText.setText(_task)
        assert _helper.work.task == _task
        assert not _helper.work.exists()
        assert _helper.work is _helper.next_work
        assert len(_helper.ui.WWorks.all_items()) == 1
        assert not _helper.ui.WTasks.selected_text()
        _helper._callback__WSave(force=True)
        assert _helper.ui.WTasks.selected_text() == _task
        assert _helper.ui.WTaskText.text() == _task
        assert _helper.work.exists()

        # Test create shot in existing seq
        _helper._callback__ToggleAdmin(True)
        _seq = _job.to_sequence(_seq_name)
        _shot = _seq.to_shot('shot020')
        assert not _shot.exists()
        _helper.ui.EntityType.select_text(_shot.sequence, catch=False)
        assert _shot.name not in _helper.ui.Entity.all_text()
        _LOGGER.info('CREATE SHOT %s', _shot)
        _helper.ui.Entity.setEditText(_shot.name)
        _helper._callback__EntityCreate(force=True, shotgrid_=False)
        assert _shot.name in _helper.ui.Entity.all_text()

        # Clean up
        _seq.delete(force=True)
        pipe.CACHE.reset()
        dcc.new_scene(force=True)

        assert not error.TRIGGERED
