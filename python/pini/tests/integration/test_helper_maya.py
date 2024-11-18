import logging
import pprint
import unittest

from pini import dcc, pipe, testing, qt
from pini.dcc import export
from pini.tools import helper
from pini.utils import single, assert_eq

from maya_pini import open_maya as pom


_LOGGER = logging.getLogger(__name__)


class TestHelper(unittest.TestCase):

    def test_farm_render_handler(self):

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

    def test_output_tab_names(self):

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

        _helper.jump_to(testing.TEST_SHOT)
        assert _helper.ui.SOutputsPane.tabText(1) == 'Shot'
        assert _helper.entity == testing.TEST_SHOT

        print()
        print('TEST JUMP TO LOOKDEV')
        _helper.jump_to(_lookdev)
        assert _helper.entity == testing.TEST_SHOT
        assert _helper.ui.SOutputsPane.current_tab_text() == 'Assets'
        assert _helper.ui.SOutputs.selected_data() == _lookdev

        # Test jump to lookdev from test asset - should select lookdev
        # in entity tab (not assets tab)
        assert _lookdev.entity == testing.TEST_ASSET
        _helper.jump_to(testing.TEST_ASSET)
        assert _helper.entity == testing.TEST_ASSET
        print()
        print('TEST JUMP TO LOOKDEV FROM ASSET')
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

    def test_shot_workflow(self, show_ctx=False, force=True):

        _progress = qt.progress_dialog('Testing shot workflow')

        _ety = pipe.CACHE.obt(testing.TMP_SHOT)
        _ety.flush(force=True)

        _test_anim_workflow(
            progress=_progress, force=force, show_ctx=show_ctx)
        _test_lighting_workflow(
            progress=_progress, force=force, show_ctx=show_ctx)
        _progress.close()

    def test_store_settings_in_scene_export_handler(self):

        testing.check_test_asset(force=True)

        _helper = helper.obt_helper()
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
        _helper.close()
        print('')
        _LOGGER.info('LAUNCH HELPER')
        _helper = helper.launch(reset_cache=False)
        assert dcc.get_scene_data('PiniQt.ExportTab.EExportPane') == 'Publish'
        print('')
        _LOGGER.info('SELECT EXPORT TAB')
        assert dcc.get_scene_data('PiniQt.ExportTab.EExportPane') == 'Publish'
        _helper.ui.MainPane.select_tab('Export')
        _LOGGER.info('SELECTED EXPORT TAB')
        assert dcc.get_scene_data('PiniQt.ExportTab.EExportPane') == 'Publish'
        assert _helper.ui.EExportPane.current_tab_text() == 'Publish'
        _m_pub = _helper.ui.EPublishHandler.selected_data()
        assert export.get_pub_refs_mode() is _import
        _m_pub.ui.References.select_text('Remove')
        assert _m_pub.ui.References.get_scene_setting() == 'Remove'
        assert export.get_pub_refs_mode() is _remove
        _helper.close()
        _LOGGER.info('HELPER CLOSED')
        print('')
        _helper = helper.launch(reset_cache=False)
        _LOGGER.info('HELPER LAUNCHED')
        _helper.ui.MainPane.select_tab('Export')
        _LOGGER.info('SELECTED EXPORT TAB')
        assert _helper.ui.EExportPane.current_tab_text() == 'Publish'
        assert export.get_pub_refs_mode() is _remove
        _helper.close()
        _helper = helper.launch(reset_cache=False)
        _helper.ui.MainPane.select_tab('Export')
        assert _helper.ui.EExportPane.current_tab_text() == 'Publish'
        _m_pub = _helper.ui.EPublishHandler.selected_data()
        assert export.get_pub_refs_mode() is _remove


def _test_anim_workflow(progress, force, show_ctx):

    _helper = helper.obt_helper()
    _shot = pipe.CACHE.obt(testing.TMP_SHOT)
    _asset = pipe.CACHE.obt(testing.TEST_ASSET)
    _rig_pub_g = _asset.find_publish(
        task='rig', ver_n='latest', tag=pipe.DEFAULT_TAG, versionless=False,
        extn='ma')
    _rig_pub = pipe.CACHE.obt(_rig_pub_g)

    # Save anim work
    progress.set_pc(5)
    dcc.new_scene(force=force)
    dcc.set_range(1001, 1005)
    _helper.ui.Refresh.click()
    _helper.jump_to(_shot)
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
    _helper.ui.MainPane.select_tab('Scene')
    _helper.ui.SOutputType.select_text('char')
    _helper.ui.SOutputTask.select_text('rig/rig')
    _helper.ui.SOutputTag.select_text(pipe.DEFAULT_TAG)
    _helper.ui.SOutputVers.select_text('latest')
    _helper.ui.SOutputs.select_data(_rig_pub, catch=False)
    _out_info = _helper.ui.SOutputInfo.text()
    assert 'bound method' not in _out_info

    # Test output context
    assert _helper.ui.SOutputs.selected_data()
    _test_ctx(
        widget=_helper.ui.SOutputs, method=_helper._context__SOutputs,
        show_ctx=show_ctx)

    # Bring in rig
    progress.set_pc(20)
    _helper.ui.SRefresh.click()
    _helper.ui.SAdd.click()
    _helper._callback__SApply(force=True)

    # Test scene ref ctx
    _rig_ref = single(_helper.ui.SSceneRefs.all_data())
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
    _blast_h.ui.Force.setChecked(True)
    _blast_h.ui.View.setChecked(False)
    _helper.ui.EBlast.click()
    assert _helper.work.outputs
    assert_eq(single(_helper.work.outputs).type_, 'blast_mov')

    # Test cache
    progress.set_pc(40)
    assert not _helper.work.find_outputs(extn='abc')
    _helper.ui.EExportPane.select_tab('Cache')
    _helper.ui.ECacheVersionUp.setChecked(False)
    _helper.ui.ECache.click()
    assert _helper.work.find_outputs(extn='abc')
    _abc = single(_helper.work.find_outputs(extn='abc'))
    assert _abc.extn == 'abc'

    return _abc


def _test_lighting_workflow(progress, force, show_ctx):

    _helper = helper.obt_helper()
    _shot = pipe.CACHE.obt(testing.TMP_SHOT)
    _asset = pipe.CACHE.obt(testing.TEST_ASSET)
    _lookdev_pub_g = _asset.find_publish(
        task='lookdev', ver_n='latest', tag=pipe.DEFAULT_TAG, versionless=False,
        extn='ma', content_type='ShadersMa')
    _lookdev_pub = pipe.CACHE.obt(_lookdev_pub_g)

    # Save lighting work
    dcc.new_scene(force=force)
    dcc.set_range(1001, 1005)
    progress.set_pc(50)
    _work_dir = _shot.find_work_dir(task='lighting', catch=True)
    if _work_dir:
        _helper.ui.WTasks.select_data(_work_dir)
    else:
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
    _abc = _shot.find_output(extn='abc', tag='test', ver_n='latest')
    _helper.ui.SOutputs.select_data(_abc)
    _helper.ui.SAdd.click()
    assert len(_helper.ui.SSceneRefs.all_items()) == 2  # abc + lookdev
    _helper._callback__SApply(force=True)

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
    _helper._callback__ERender(force=True, render_=False)


def _test_ctx(widget, method, show_ctx):

    _pos = widget.rect().center()
    _menu = qt.CMenu(widget)
    method(_menu)
    if show_ctx:
        _menu.exec_(widget.mapToGlobal(_pos))
