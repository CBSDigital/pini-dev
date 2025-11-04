import logging
import os
import pprint
import unittest

from maya import cmds

from pini import dcc, pipe, testing, qt
from pini.pipe import cache
from pini.dcc import export
from pini.tools import helper
from pini.utils import single, assert_eq, ints_to_str

from pini.dcc.export.eh_publish.ph_maya import phm_basic

from maya_pini import open_maya as pom
from maya_pini.utils import process_deferred_events


_LOGGER = logging.getLogger(__name__)


class TestHelper(unittest.TestCase):

    def test_farm_render_handler(self):

        if cmds.objExists('blah'):
            cmds.delete('blah')
        _farm_rh = dcc.find_export_handler('render', filter_='farm', catch=True)
        if not _farm_rh:
            return

        _default_lyr = pom.find_render_layer('masterLayer')
        _blah_lyr = pom.find_render_layer('blah', catch=True)
        if not _blah_lyr:
            _blah_lyr = pom.create_render_layer('blah')
        assert _blah_lyr

        _helper = helper.obt_helper()
        _helper.ui.MainPane.select_tab('Export')
        _helper.ui.EExportPane.select_tab('Render')
        _helper.ui.ERenderHandler.select_data(_farm_rh)

        _farm_rh._build_layers_elems()
        _farm_rh.ui.Layers.select(_blah_lyr, replace=True)
        assert not _default_lyr.is_renderable()
        assert _blah_lyr.is_renderable()
        _farm_rh.ui.Layers.select(_default_lyr, replace=True)
        assert _default_lyr.is_renderable()
        assert not _blah_lyr.is_renderable()

    def test_model_reps(self, show_ctx=False):

        _mdl = testing.find_test_model()
        pprint.pprint(_mdl.find_reps())
        assert _mdl.find_reps()
        assert _mdl.find_reps(extn='abc')
        assert _mdl.find_reps(extn='fbx', dcc_=None)
        _abc = _mdl.find_rep(extn='abc')
        assert _abc in _mdl.entity.find_publishes()
        assert _abc in _mdl.job.find_publishes()
        assert _abc.is_latest()
        assert isinstance(_abc, cache.CCPOutputFile)
        _fbx = _mdl.find_rep(extn='fbx')

        _helper = helper.obt_helper()
        _helper.ui.MainPane.select_tab('Scene')
        _helper.jump_to(_mdl)
        _helper.stage_import(_mdl, reset=True)

        # Check scene refs context menu
        _helper.ui.SSceneRefs.select_row(0)
        _pos = _helper.ui.SSceneRefs.rect().center()
        _menu = qt.CMenu(_helper.ui.SSceneRefs)
        _helper._context__SSceneRefs(_menu)
        if show_ctx:
            _menu.exec_(_helper.ui.SSceneRefs.mapToGlobal(_pos))
        assert _menu.actions()
        _menu.deleteLater()

        # Check abc label
        print()
        _LOGGER.info(' - ABC %s', _abc)
        _helper.jump_to(_abc)
        assert _abc == _abc.to_ghost()
        assert _abc in [_abc.to_ghost()]
        _LOGGER.info(' - ABC %s', _abc)
        pprint.pprint(_helper.ui.SOutputType.selected_data())
        assert _abc.path in [_out.path for _out in _helper.ui.SOutputType.selected_data()]
        assert _abc in _helper.ui.SOutputType.selected_data()
        assert _helper.ui.SOutputs.selected_data() == _abc
        _item = _helper.ui.SOutputs.selected_item()
        assert _item.label == 'test (model abc)'

        # Check fbx label
        print()
        _LOGGER.info(' - FBX %s', _fbx)
        _helper.jump_to(_fbx)
        assert _helper.ui.SOutputs.selected_data() == _fbx
        _item = _helper.ui.SOutputs.selected_item()
        assert _item.label == 'test (model fbx)'

        _helper.ui.SReset.click()

    def test_output_tab_names(self):

        dcc.new_scene(force=True)

        _lookdev = testing.find_test_lookdev()
        _rig = testing.find_test_rig()
        _abc = testing.find_test_abc()
        _ren = testing.find_test_render()

        assert not _lookdev.is_media()
        assert not _rig.is_media()
        assert not _abc.is_media()
        assert _ren.is_media()

        _helper = helper.obt_helper()
        _helper.ui.MainPane.select_tab('Scene')
        _helper.jump_to(testing.TEST_ASSET)

        assert _helper.ui.SOutputsPane.tabText(0) == 'Assets'
        assert _helper.ui.SOutputsPane.tabText(1) == 'Asset'

        print()
        print('TEST JUMP TO TEST SHOT ' + testing.TEST_SHOT.path)
        _helper.jump_to(testing.TEST_SHOT)
        assert _helper.entity == testing.TEST_SHOT
        assert _helper.ui.SOutputsPane.tabText(1) == 'Shot'

        print()
        print('TEST JUMP TO LOOKDEV')
        _helper.jump_to(_lookdev)
        assert _helper.ui.SOutputsPane.current_tab_text() == 'Assets'
        assert _helper.ui.SOutputs.selected_data() == _lookdev

        # Test jump to lookdev from test asset - should select lookdev
        # in entity tab (not assets tab)
        assert _lookdev.entity == testing.TEST_ASSET
        _helper.jump_to(testing.TEST_ASSET)
        assert _helper.entity == testing.TEST_ASSET
        print()
        print('TEST JUMP TO LOOKDEV FROM ASSET ' + _lookdev.path)
        _helper.jump_to(_lookdev)
        assert _helper.entity == testing.TEST_ASSET
        assert _helper.ui.SOutputsPane.tabText(1) == 'Asset'
        assert _helper.ui.SOutputsPane.current_tab_text() == 'Asset'
        assert _helper.ui.SOutputs.selected_data() == _lookdev

        print()
        print('TEST JUMP TO RIG')
        _helper.jump_to(_rig)
        assert _helper.ui.SOutputsPane.current_tab_text() == 'Asset'
        assert _helper.ui.SOutputs.selected_data() == _rig

        print()
        print('TEST JUMP TO ABC')
        _helper.jump_to(_abc)
        assert _helper.ui.SOutputsPane.current_tab_text() == 'Shot'
        assert _helper.ui.SOutputs.selected_data() == _abc

        print()
        print('TEST JUMP TO RENDER')
        _helper.jump_to(_ren)
        assert _helper.ui.SOutputsPane.current_tab_text() == 'Media'
        assert _helper.ui.SOutputs.selected_data() == _ren

    def test_export_range_opts(self):

        _helper = helper.obt_helper()
        _helper.ui.MainPane.select_tab('Export')
        _helper.ui.EExportPane.select_tab('Render')
        _helper.ui.ERenderHandler.select('Local')

        _ren = _helper.ui.ERenderHandler.selected_data()
        _custom = '1001,1003,1010-1015'
        _LOGGER.info('REN %s', _ren)

        dcc.set_range(1001, 1020)
        dcc.set_frame(1001)
        _ren.ui.RangeStepSize.set_val(3)
        _ren.ui.RangeCustom.setText(_custom)
        assert dcc.t_range() == (1001, 1020)
        assert dcc.t_frame() == 1001

        print()
        for _mode, _frame_str in [
                ('From timeline', '1001-1019x3'),
                ('Current frame', '1001'),
                ('Custom', _custom),
        ]:
            _LOGGER.info(' - TEST %s', _mode)
            _ren.ui.Range.select(_mode)
            _frames = _ren.ui.to_frames()
            _frames_s = ints_to_str(_frames)
            _LOGGER.info(' - FRAMES %s %s', _frames_s, _frames)
            assert_eq(_frame_str, _frames_s)
            assert f'frames: {_frame_str}' == _ren.ui.RangeFramesLabel.text()
        print()

        # Check manual range
        _helper.ui.EExportPane.select_tab('Cache')
        _cache = _helper.ui.ECacheHandler.selected_data()
        assert _cache.ui.range_mode == 'Continuous'
        _cache.ui.Range.select('From timeline')
        assert _cache.ui.RangeFramesLabel.text() == 'frames: 1001-1020'
        assert_eq(ints_to_str(_cache.ui.to_frames()), '1001-1020')
        _cache.ui.Range.select('Manual')
        _cache.ui.RangeManualStart.setValue(1005)
        _cache.ui.RangeManualEnd.setValue(1010)
        assert _cache.ui.RangeFramesLabel.text() == 'frames: 1005-1010'
        assert_eq(ints_to_str(_cache.ui.to_frames()), '1005-1010')
        _helper.ui.EExportPane.select_tab('Render')
        _helper.ui.EExportPane.select_tab('Cache')
        assert _cache.ui.RangeManualStart.value() == 1005
        assert _cache.ui.RangeManualEnd.value() == 1010

    def test_shot_workflow(self, show_ctx=False, force=True):

        _progress = qt.progress_dialog('Testing shot workflow')

        _LOGGER.info('TMP SHOT %s', testing.TMP_SHOT)
        _ety = pipe.CACHE.obt(testing.TMP_SHOT)
        if not _ety:
            testing.TMP_SHOT.create(force=True)
            pipe.CACHE.reset()
            _ety = pipe.CACHE.obt(testing.TMP_SHOT)
            assert _ety
        _ety.flush(force=True)

        _test_anim_workflow(
            progress=_progress, force=force, show_ctx=show_ctx)
        _test_lighting_workflow(
            progress=_progress, force=force, show_ctx=show_ctx)
        _progress.close()

    def test_store_settings_in_scene_export_handler(self):

        _helper = helper.obt_helper(reset_cache=False)
        _import = export.PubRefsMode.IMPORT_TO_ROOT
        _remove = export.PubRefsMode.REMOVE

        # Apply refs mode
        _ety_c = pipe.CACHE.obt(testing.TEST_ASSET)
        _work_dir = _ety_c.find_work_dir('model', dcc_='maya')
        _work = _work_dir.to_work().find_latest()
        _LOGGER.info(' - WORK %s', _work)
        _work.load(force=True)
        _helper.jump_to(_work)
        _helper.ui.MainPane.select_tab('Export')
        _helper.ui.EExportPane.select_tab('Publish', emit=True)
        assert dcc.get_scene_data('PiniQt.ExportTab.EExportPane') == 'Publish'
        _m_pub = _helper.ui.EPublishHandler.selected_data()
        assert _m_pub.NAME == 'Maya Model Publish'
        assert _m_pub.ui.References.save_policy is qt.SavePolicy.SAVE_IN_SCENE
        _m_pub.ui.References.select_text('Import into root namespace', emit=True)
        _LOGGER.info(' - SETTING KEY %s', _m_pub.ui.References.settings_key)
        assert _m_pub.ui.References.settings_key == 'PiniQt.Publish.References'
        assert _m_pub.ui.References.has_scene_setting()
        assert _m_pub.ui.References.get_scene_setting() == 'Import into root namespace'
        assert _m_pub.ui.References.selected_data() is _import
        assert export.get_pub_refs_mode() is _import
        assert dcc.get_scene_data('PiniQt.ExportTab.EExportPane') == 'Publish'

        # Check setting maintained
        _helper.delete()
        print('')
        _LOGGER.info('LAUNCH HELPER')
        _helper = helper.launch(reset_cache=False)
        assert dcc.get_scene_data('PiniQt.ExportTab.EExportPane') == 'Publish'
        assert dcc.get_scene_data('PiniQt.Publish.References') == 'Import into root namespace'
        assert _m_pub.ui.References.currentText() == 'Import into root namespace'
        print('')
        _LOGGER.info('SELECT EXPORT TAB')
        _helper.ui.MainPane.select_tab('Export')
        _LOGGER.info('SELECTED EXPORT TAB')
        assert dcc.get_scene_data('PiniQt.ExportTab.EExportPane') == 'Publish'
        assert _helper.ui.EExportPane.current_tab_text() == 'Publish'
        _m_pub = _helper.ui.EPublishHandler.selected_data()
        assert export.get_pub_refs_mode() is _import
        print()
        _LOGGER.info(' - SELECTING "Remove"')
        assert _m_pub.ui.References.save_policy == qt.SavePolicy.SAVE_IN_SCENE
        _m_pub.ui.References.select_text('Remove')
        assert _m_pub.ui.References.settings_key == 'PiniQt.Publish.References'
        assert _m_pub.ui.References.settings_key == phm_basic._PUB_REFS_MODE_KEY
        _LOGGER.info(' - SETTING %s', _m_pub.ui.References.get_scene_setting())
        assert _m_pub.ui.References.get_scene_setting() == 'Remove'
        assert export.get_pub_refs_mode() is _remove
        _helper.delete()
        _LOGGER.info('HELPER CLOSED (DELETED')
        process_deferred_events()
        assert not helper.is_active()
        print('')
        _helper = helper.launch(reset_cache=False)
        process_deferred_events()
        _LOGGER.info('HELPER LAUNCHED')
        _helper.ui.MainPane.select_tab('Export')
        _LOGGER.info('SELECTED EXPORT TAB')
        assert _helper.ui.EExportPane.current_tab_text() == 'Publish'
        assert export.get_pub_refs_mode() is _remove
        _helper.delete()
        _helper = helper.launch(reset_cache=False)
        _helper.ui.MainPane.select_tab('Export')
        assert _helper.ui.EExportPane.current_tab_text() == 'Publish'
        _m_pub = _helper.ui.EPublishHandler.selected_data()
        assert export.get_pub_refs_mode() is _remove


def _test_anim_workflow(progress, force, show_ctx):

    _helper = helper.obt_helper()
    _shot = pipe.CACHE.obt(testing.TMP_SHOT)
    _asset = pipe.CACHE.obt(testing.TEST_ASSET)
    _rig_pub = testing.find_test_rig()

    # Save anim work
    progress.set_pc(5)
    dcc.new_scene(force=force)
    dcc.set_range(1001, 1005)
    _helper.ui.Refresh.click()
    _helper.jump_to(_shot)
    assert _helper.entity == testing.TMP_SHOT
    _helper.ui.MainPane.select_tab('Work')
    assert _helper.entity == _shot
    assert _helper.entity == testing.TMP_SHOT
    _work_dir = _shot.find_work_dir('anim', dcc_=dcc.NAME, catch=True)
    _LOGGER.info('WORK DIR %s', _work_dir)
    if _work_dir:
        _helper.ui.WTasks.select_data(_work_dir)
    else:
        if not _helper.ui.ToggleAdmin.isChecked():
            _helper.ui.ToggleAdmin.click()
        _helper.ui.WTaskText.setText('anim')
    assert _helper.entity == testing.TMP_SHOT
    _helper.ui.WTagText.setText('test')
    _helper.ui.WWorks.select_item(_helper.ui.WWorks.all_items()[-1])
    assert _helper.work.entity == testing.TMP_SHOT
    assert _helper.work.tag == 'test'
    assert _helper.work.pini_task == 'anim'
    assert _helper.work.ver_n == 1
    _helper._callback__WSave(force=True)
    if _helper.ui.ToggleAdmin.isChecked():
        _helper.ui.ToggleAdmin.click()
    assert not _helper.ui.ToggleAdmin.isChecked()

    # Flush outputs
    progress.set_pc(10)
    _updated = False
    for _out in _helper.work.outputs:
        _LOGGER.info(' - REMOVE %s', _out)
        _updated = True
        assert pipe.to_entity(_out) == testing.TMP_SHOT
        _out.delete(force=True)
    if _updated:
        _helper.work.find_outputs(force=True)
    assert not _helper.work.outputs

    # Check work context menu
    assert _helper.work
    _pos = _helper.ui.WWorks.rect().center()
    _LOGGER.info(' - %s', _pos)
    _menu = qt.CMenu(_helper.ui.WWorks)
    _helper._context__WWorks(_menu)
    if show_ctx:
        _menu.exec_(_helper.ui.WWorks.mapToGlobal(_pos))
    assert _menu.actions()
    _menu.deleteLater()

    # Select rig in outputs list
    print()
    _LOGGER.info(' - RIG PUB %s', _rig_pub)
    _helper.jump_to(_rig_pub)
    assert _helper.ui.SOutputs.selected_data() == _rig_pub
    _out_info = _helper.ui.SOutputInfo.text()
    assert 'bound method' not in _out_info

    # Test output context
    assert _helper.ui.SOutputs.selected_data()
    _test_ctx(
        widget=_helper.ui.SOutputs, method=_helper._context__SOutputs,
        show_ctx=show_ctx)

    # Bring in rig
    progress.set_pc(20)
    _helper.ui.SReset.click()
    _helper.ui.SRefresh.click()
    _helper.ui.SAdd.click()
    _helper.ui.SAdd.click()
    _helper.apply_updates(force=True)

    # Test scene ref ctx
    _rig_ref = _helper.ui.SSceneRefs.all_data()[0]
    _helper.ui.SSceneRefs.select_data(_rig_ref)
    assert _helper.ui.SSceneRefs.selected_data()
    _test_ctx(
        widget=_helper.ui.SSceneRefs, method=_helper._context__SSceneRefs,
        show_ctx=show_ctx)

    # Test blast
    progress.set_pc(30)
    assert not _helper.work.outputs
    _helper.ui.MainPane.select_tab('Export')
    _helper.ui.EExportPane.select_tab('Blast')
    _blast_h = _helper.ui.EBlastHandler.selected_data()
    assert _blast_h

    _vid_fmt = os.environ.get('PINI_VIDEO_FORMAT', 'mp4')
    _blast_h.ui.Format.select_text(_vid_fmt)
    _blast_h.ui.ForceReplace.setChecked(True)
    _blast_h.ui.View.setChecked(False)
    _blast_h.exec_from_ui(force=True)
    _LOGGER.info(' - WORK %s', _helper.work)
    _helper.ui.MainPane.select_tab('Work')
    assert _helper.work.outputs
    assert_eq(single(_helper.work.outputs).type_, 'blast_mov')

    # Test cache
    progress.set_pc(40)
    assert not _helper.work.find_outputs(extn='abc')
    _helper.ui.MainPane.select_tab('Export')
    _helper.ui.EExportPane.select_tab('Cache')
    _exp = _helper.ui.ECacheHandler.selected_data()
    assert (
        _exp.ui.Cacheables.all_data() ==
        _exp.ui.Cacheables.selected_datas())
    _exp.ui.VersionUp.setChecked(False)
    _exp.ui.Notes.setText('integration test')
    _exp.exec_from_ui(force=True)
    assert _helper.work.find_outputs(extn='abc')
    assert len(_helper.work.find_outputs(extn='abc')) == 2
    _abc = _helper.work.find_outputs(extn='abc')[0]
    assert _abc.extn == 'abc'

    return _abc


def _test_lighting_workflow(progress, force, show_ctx):

    _helper = helper.obt_helper()
    _shot = pipe.CACHE.obt(testing.TMP_SHOT)
    _asset = pipe.CACHE.obt(testing.TEST_ASSET)
    _lookdev_pub = testing.find_test_lookdev()

    # Save lighting work
    dcc.new_scene(force=force)
    dcc.set_range(1001, 1005)
    progress.set_pc(50)
    _work_dir = _shot.find_work_dir(task='lighting', filter_='-mod', catch=True)
    if _work_dir:
        _helper.ui.WTasks.select_data(_work_dir)
    else:
        assert pipe.MASTER == 'disk'
        if not _helper.ui.ToggleAdmin.isChecked():
            _helper.ui.ToggleAdmin.click()
        _helper.ui.WTaskText.setText('lighting')
    _helper.ui.WTagText.setText('test')
    assert _helper.work.ver_n == 1
    assert _helper.work.pini_task == 'lighting'
    assert _helper.work.tag == 'test'
    _helper._callback__WSave(force=True)
    if _helper.ui.ToggleAdmin.isChecked():
        _helper.ui.ToggleAdmin.click()
    assert not _helper.ui.ToggleAdmin.isChecked()

    # Bring in abc
    progress.set_pc(60)
    _helper.ui.MainPane.select_tab('Scene')
    pprint.pprint(_shot.find_outputs(extn='abc', tag='test'))
    _abc = _shot.find_output(
        extn='abc', tag='test', output_name='test01', ver_n='latest')
    assert _abc.metadata['src_ref']
    _out = pipe.CACHE.obt_output(_abc.metadata['src_ref'])
    assert _out
    assert _out.find_lookdev_shaders()
    assert _abc.find_lookdev_shaders()
    _helper.ui.SOutputs.select_data(_abc)
    _helper.ui.SLookdev.select_text('Reference')
    _helper.ui.SAdd.click()
    assert len(_helper.ui.SSceneRefs.all_items()) == 2  # abc + lookdev
    _helper.apply_updates(force=True)

    # Test lookdev publish ctx
    progress.set_pc(70)
    _helper.ui.SOutputsPane.select_tab(_helper.ui.SAssetsTab)
    _helper.jump_to(_lookdev_pub)
    assert _helper.ui.SOutputs.selected_data() == _lookdev_pub
    _test_ctx(
        widget=_helper.ui.SOutputs, method=_helper._context__SOutputs,
        show_ctx=show_ctx)

    # Test render
    progress.set_pc(80)
    _helper.ui.MainPane.select_tab('Export')
    _helper.ui.EExportPane.select_tab('Render')
    _render_h = _helper.ui.ERenderHandler.selected_data()
    assert _render_h
    _render_h.ui.VersionUp.setChecked(False)
    if _render_h.NAME == 'Maya Farm Render':
        _render_h.ui.LimitGrps.setText('gpu-nvidia-rtx,maya-2023,redshift')
    _render_h.exec_from_ui(force=True, render_=False)


def _test_ctx(widget, method, show_ctx):

    _pos = widget.rect().center()
    _menu = qt.CMenu(widget)
    method(_menu)
    if show_ctx:
        _menu.exec_(widget.mapToGlobal(_pos))
