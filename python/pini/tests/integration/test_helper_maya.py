import unittest
import logging

from pini import dcc, pipe, testing, qt
from pini.dcc import export_handler
from pini.tools import helper, error

from maya_pini import open_maya as pom


_LOGGER = logging.getLogger(__name__)


class TestHelper(unittest.TestCase):

    def setUp(self):
        assert not error.TRIGGERED
        if not helper.is_active():
            helper.launch(reset_cache=False)
        assert not error.TRIGGERED

    def test_farm_render_handler(self):

        _farm_rh = dcc.find_export_handler('render', filter_='farm', catch=True)
        if not _farm_rh:
            return

        _default_lyr = pom.find_render_layer('masterLayer')
        _blah_lyr = pom.find_render_layer('blah', catch=True)
        if not _blah_lyr:
            _blah_lyr = pom.create_render_layer('blah')
        assert _blah_lyr

        _helper = helper.DIALOG
        _helper.ui.MainPane.select_tab('Export')
        _helper.ui.EExportPane.select_tab('Render')
        _helper.ui.ERenderHandler.select_data(_farm_rh)

        _farm_rh.ui.Layers.select(_blah_lyr, replace=True)
        assert not _default_lyr.is_renderable()
        assert _blah_lyr.is_renderable()
        _farm_rh.ui.Layers.select(_default_lyr, replace=True)
        assert _default_lyr.is_renderable()
        assert not _blah_lyr.is_renderable()

    def test_store_settings_in_scene_export_handler(self):

        _helper = helper.DIALOG
        _import = export_handler.ReferencesMode.IMPORT_INTO_ROOT_NAMESPACE
        _remove = export_handler.ReferencesMode.REMOVE

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
        assert export_handler.get_publish_references_mode() is _import
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
        assert export_handler.get_publish_references_mode() is _import
        _m_pub.ui.References.select_text('Remove')
        assert _m_pub.ui.References.get_scene_setting() == 'Remove'
        assert export_handler.get_publish_references_mode() is _remove
        _helper.close()
        _LOGGER.info('HELPER CLOSED')
        print('')
        _helper = helper.launch(reset_cache=False)
        _LOGGER.info('HELPER LAUNCHED')
        _helper.ui.MainPane.select_tab('Export')
        _LOGGER.info('SELECTED EXPORT TAB')
        assert _helper.ui.EExportPane.current_tab_text() == 'Publish'
        assert export_handler.get_publish_references_mode() is _remove
        _helper.close()
        _helper = helper.launch(reset_cache=False)
        _helper.ui.MainPane.select_tab('Export')
        assert _helper.ui.EExportPane.current_tab_text() == 'Publish'
        _m_pub = _helper.ui.EPublishHandler.selected_data()
        assert export_handler.get_publish_references_mode() is _remove
