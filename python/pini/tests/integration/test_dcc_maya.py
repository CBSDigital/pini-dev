# pylint: disable=import-error

import logging
import pprint
import unittest

from maya import cmds

from pini import dcc, testing, pipe, qt
from pini.dcc import pipe_ref, export
from pini.tools import error, helper
from pini.utils import single, assert_eq

from pini.dcc.export.eh_publish.ph_maya import phm_basic

from maya_pini import open_maya as pom

_LOGGER = logging.getLogger(__name__)


class TestDCC(unittest.TestCase):

    def test_pub_refs_mode(self):

        dcc.new_scene(force=True)

        _ety = pipe.CACHE.obt(testing.TEST_ASSET)
        _work_dir = _ety.find_work_dir(
            'rig', dcc_=dcc.NAME)
        _work = _work_dir.to_work(tag='tmp')
        _work.save(force=True)

        # Test without helper
        assert not dcc.get_scene_data(phm_basic._PUB_REFS_MODE_KEY)
        _mode = export.get_pub_refs_mode()
        _LOGGER.info('MODE %s', _mode)
        assert _mode is export.PubRefsMode.REMOVE
        export.set_pub_refs_mode(export.PubRefsMode.IMPORT_TO_ROOT)
        _mode = export.get_pub_refs_mode()
        assert _mode
        _LOGGER.info('MODE %s', _mode)
        assert_eq(_mode, export.PubRefsMode.IMPORT_TO_ROOT)
        export.set_pub_refs_mode(export.PubRefsMode.REMOVE)
        _mode = export.get_pub_refs_mode()
        assert _mode
        _LOGGER.info('MODE %s', _mode)
        assert_eq(_mode, export.PubRefsMode.REMOVE)

        # Test with helper
        _helper = helper.obt_helper(reset_cache=False)
        _helper.ui.MainPane.select_tab('Export')
        _helper.ui.EExportPane.select_tab('Publish')
        _handler = _helper.ui.EPublishHandler.selected_data()
        assert _handler.ui.References.currentText() == 'Remove'
        export.set_pub_refs_mode(export.PubRefsMode.IMPORT_TO_ROOT)
        assert _handler.ui.References.currentText() == 'Import into root namespace'

    def test_swap_refs(self):

        _LOGGER.info('TEST SWAP REFS')

        if 'arnold' not in dcc.allowed_renderers():
            _LOGGER.info(' - TEST DISABLED OUTSIDE ARNOLD')
            return

        _LOGGER.info(' - CHECKED TEST ASSET')

        _tag = testing.TEST_JOB.cfg['tokens']['tag']['default']
        _asset_c = pipe.CACHE.obt(testing.TEST_ASSET)

        # Clean up
        dcc.new_scene(force=True)
        assert not cmds.objExists('CHAR')

        # Test mapping
        _model_g = _asset_c.find_publish(
            task='model', ver_n='latest', tag=_tag, versionless=False,
            extn='ma')
        _LOGGER.info('MODEL G %s', _model_g)
        _model = pipe.CACHE.obt(_model_g)
        assert _model
        assert _model.find_reps()
        _ass_gz = _model.find_rep(extn='gz')
        assert _ass_gz
        _LOGGER.info('ASS GZ %s', _ass_gz.path)
        _rig = _ass_gz.find_rep(task='rig')
        assert _rig
        _LOGGER.info('MODEL %s', _rig.find_rep(task='model'))
        assert _rig.find_rep(task='model') == _model
        assert _ass_gz.find_rep(task='model') == _model

        # Create model ref
        _ref = dcc.create_ref(_model, namespace='test', group='BLAH')
        pom.CPoint(0, 4, 0).apply_to(_ref.top_node)
        assert _ref.output == _model
        assert isinstance(_ref, pipe_ref.CMayaRef)
        assert _ref.node.ty.get_val() == 4
        assert _ref.node.to_parent().name() == 'BLAH'
        assert not cmds.objExists('CHAR')

        # Swap to ass gz
        _ass_gz = _ref.find_rep(extn='gz')
        assert _ass_gz
        _ref = _ref.update(_ass_gz)
        assert _ref.output == _ass_gz
        assert isinstance(_ref, pipe_ref.CMayaAiStandIn)
        _LOGGER.info(' - REF %s %s %s', _ref, _ref.node, _ref.top_node)
        assert _ref.top_node.ty.get_val() == 4
        assert _ref.top_node.to_parent().name() == 'BLAH'
        assert _ref.namespace == 'test'
        assert not cmds.objExists('CHAR')

        # Swap to rig
        _rig = _ref.find_rep(task='rig')
        assert _rig
        _ref = _ref.update(_rig)
        assert _ref.output == _rig
        assert isinstance(_ref, pipe_ref.CMayaRef)
        assert _ref.top_node.ty.get_val() == 4
        assert _ref.top_node.to_parent().name() == 'BLAH'
        assert not cmds.objExists('CHAR')
        assert _ref.namespace == 'test'

        # Test no parent
        _ref = dcc.create_ref(_model, namespace='test2', group=None)
        assert not _ref.top_node.to_parent()
        _ref = _ref.update(_ass_gz)
        assert not _ref.top_node.to_parent()

    def test_version_up_publish(self):

        _progress = qt.progress_dialog('Test version up publish')
        _ety = testing.TMP_ASSET
        _ety.flush(force=True)
        pipe.CACHE.reset()
        _ety_c = pipe.CACHE.obt(testing.TMP_ASSET)
        pprint.pprint(_ety_c.outputs)
        assert not _ety_c.outputs
        assert not _ety_c.find_outputs()

        _progress.set_pc(10)
        _handler = dcc.find_export_handler(
            'publish', filter_='basic', catch=True)
        _handler.ui = None  # Reset any leftover ui elems

        # Save basic scene to publish
        _progress.set_pc(20)
        dcc.new_scene(force=True)
        cmds.polyCube()
        _work = testing.TMP_ASSET.to_work(task='mod')
        _LOGGER.info('WORK %s', _work.path)
        _work.save(force=True)
        assert not _ety_c.find_outputs()
        _work_c = pipe.CACHE.obt_work(_work)

        # Test publish without PiniHelper
        _progress.set_pc(30)
        _LOGGER.info(' - CUR WORK OUTS %s', _work_c.find_outputs())
        if _work_c.outputs:
            _work_c.find_outputs(force=True)
        assert pipe.CACHE.cur_job is _ety_c.job
        _LOGGER.info(' - WORK C OUTS %s', _work_c.find_outputs())
        assert not _work_c.find_outputs()
        assert not _work_c.outputs
        _outs = _handler.exec(force=True, version_up=False, bkp=False)
        _ety_c = pipe.CACHE.obt(_ety_c)
        assert pipe.CACHE.cur_job is _ety_c.job
        _LOGGER.info(' - OUTS %s', _outs)
        _out = single([_out for _out in _outs if _out.extn == 'ma'])
        _LOGGER.info(' - OUT %s', _outs)
        _work_c = pipe.CACHE.obt_work(_work_c)
        assert pipe.cur_work().find_outputs()
        assert _work_c.find_outputs()
        assert _work_c.outputs
        assert pipe.CACHE.cur_entity is _work_c.entity
        assert pipe.CACHE.cur_work_dir is _work_c.work_dir
        assert pipe.CACHE.cur_work is _work_c
        _work_dir_c = pipe.CACHE.cur_entity.obt_work_dir(_work_c.work_dir)
        _LOGGER.info('WORK DIR C %s', _work_dir_c)
        assert _work_dir_c is pipe.CACHE.cur_work_dir
        assert _work_dir_c is _work_c.work_dir
        _LOGGER.info('WORK C %s', _work_c)
        _LOGGER.info('OUT %s', _out)
        assert _out in _work_c.find_outputs()
        assert _out in _work_c.outputs

        # Version up
        print('\nTEST VERSION UP')
        assert pipe.CACHE.cur_job is _ety_c.job
        _progress.set_pc(40)
        _next = pipe.version_up()
        _ety_c = pipe.CACHE.obt(_ety_c)
        assert pipe.CACHE.cur_job is _ety_c.job
        assert isinstance(_next, pipe.CPWork)
        # assert not isinstance(_next, cache.CCPWork)
        assert pipe.CACHE.cur_work
        assert pipe.CACHE.cur_work.ver_n == 2
        _work_c = pipe.CACHE.obt_work(_next)
        _LOGGER.info(' - JOB %s %s', pipe.CACHE.cur_job, _ety_c.job)
        assert pipe.CACHE.cur_job is _ety_c.job

        # Test publish with PiniHelper
        print('\nTEST PUBLISH')
        _progress.set_pc(50)
        _LOGGER.info(' - LAUNCH HELPER')
        _helper = helper.obt_helper(reset_cache=False)
        _helper.jump_to(_work_c)
        _LOGGER.info(' - JOB %s %s', _helper.job, pipe.CACHE.cur_job)
        assert pipe.CACHE.cur_job is _ety_c.job
        assert pipe.CACHE.cur_job is _helper.job
        assert _helper.job == pipe.CACHE.cur_job
        assert _helper.job is pipe.CACHE.cur_job
        assert _helper.work.exists()
        assert _helper.work == pipe.cur_work()
        _LOGGER.info(' - ETY %s %s', _helper.entity, pipe.CACHE.cur_entity)
        assert _helper.entity == pipe.CACHE.cur_entity
        assert _helper.entity is pipe.CACHE.cur_entity
        assert _helper.work_dir is pipe.CACHE.cur_work_dir
        assert _helper.work is pipe.CACHE.cur_work

        # Publish
        _progress.set_pc(70)
        _helper.ui.MainPane.select_tab('Export')
        _exp = _helper.ui.EPublishHandler.selected_data()
        _LOGGER.info(' - EXPORTER %s', _exp)
        _exp.ui.VersionUp.setChecked(False)
        _exp.ui.Fbx.setChecked(False)
        _helper.ui.MainPane.select_tab('Export')
        _helper.ui.EExportPane.select_tab('Publish')
        _out = single(_exp.exec_from_ui(force=True))
        _LOGGER.info('CUR ETY %s', pipe.CACHE.cur_entity)
        assert _helper.entity is pipe.CACHE.cur_entity
        assert _helper.work_dir is pipe.CACHE.cur_work_dir
        assert _helper.work is pipe.CACHE.cur_work
        _work_c = pipe.CACHE.obt_work(_work_c)
        assert pipe.cur_work().find_outputs()
        assert _work_c.find_outputs()
        assert _work_c.outputs
        assert pipe.CACHE.cur_entity is _work_c.entity
        assert pipe.CACHE.cur_work_dir is _work_c.work_dir
        assert pipe.CACHE.cur_work is _work_c
        _work_dir_c = pipe.CACHE.cur_entity.obt_work_dir(_work_c.work_dir)
        assert _work_dir_c is pipe.CACHE.cur_work_dir
        assert _work_dir_c is _work_c.work_dir
        assert _out in _work_c.find_outputs()
        assert _out in _work_c.outputs

        # Version up
        _progress.set_pc(90)
        _helper.ui.WWorks.select_data(_helper.next_work)
        _helper.ui.WSave.click()
        assert pipe.CACHE.cur_work.ver_n == 3
        assert not error.TRIGGERED

        _progress.close()
