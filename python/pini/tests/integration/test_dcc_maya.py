import logging
import pprint
import unittest

from maya import cmds

from pini import dcc, testing, pipe
from pini.dcc import pipe_ref
from pini.pipe import cache
from pini.tools import error, helper
from pini.utils import single

from maya_pini import open_maya as pom

_LOGGER = logging.getLogger(__name__)


class TestDCC(unittest.TestCase):

    def test_swap_refs(self):

        _LOGGER.info('TEST SWAP REFS')

        if 'arnold' not in dcc.allowed_renderers():
            _LOGGER.info(' - TEST DISABLED OUTSIDE ARNOLD')
            return

        testing.check_test_asset()
        _LOGGER.info(' - CHECKED TEST ASSET')

        _tag = testing.TEST_JOB.cfg['tokens']['tag']['default']
        _asset_c = pipe.CACHE.obt(testing.TEST_ASSET)

        # Clean up
        dcc.new_scene(force=True)
        assert not cmds.objExists('CHAR')

        # Test mapping
        _model_g = _asset_c.find_publish(
            task='model', ver_n='latest', tag=_tag, versionless=False)
        _LOGGER.info('MODEL G %s', _model_g)
        _model = pipe.CACHE.obt(_model_g)
        assert _model
        assert _model.find_reps()
        _ass_gz = _model.find_rep(extn='gz')
        _rig = _ass_gz.find_rep(task='rig')
        _LOGGER.info('MODEL %s', _rig.find_rep(task='model'))
        assert _rig.find_rep(task='model') == _model
        assert _ass_gz.find_rep(task='model') == _model

        # Create model ref
        _ref = dcc.create_ref(_model, namespace='test', group='BLAH')
        pom.CPoint(0, 4, 0).apply_to(_ref.node)
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
        assert _ref.node.ty.get_val() == 4
        assert _ref.node.to_parent().name() == 'BLAH'
        assert _ref.namespace == 'test'
        assert not cmds.objExists('CHAR')

        # Swap to rig
        _rig = _ref.find_rep(task='rig')
        assert _rig
        _ref = _ref.update(_rig)
        assert _ref.output == _rig
        assert isinstance(_ref, pipe_ref.CMayaRef)
        assert _ref.node.ty.get_val() == 4
        assert _ref.node.to_parent().name() == 'BLAH'
        assert not cmds.objExists('CHAR')
        assert _ref.namespace == 'test'

        # Test no parent
        _ref = dcc.create_ref(_model, namespace='test2', group=None)
        assert not _ref.node.to_parent()
        _ref = _ref.update(_ass_gz)
        assert not _ref.node.to_parent()

    def test_version_up_publish(self):

        testing.TMP_ASSET.flush(force=True)
        pipe.CACHE.reset()
        _ety_c = pipe.CACHE.obt(testing.TMP_ASSET)
        pprint.pprint(_ety_c.outputs)
        assert not _ety_c.find_outputs()

        _handler = dcc.find_export_handler(
            'publish', filter_='basic', catch=True)
        _handler.ui = None  # Reset any leftover ui elems

        # Save basic scene to publish
        dcc.new_scene(force=True)
        cmds.polyCube()
        _work = testing.TMP_ASSET.to_work(task='mod')
        _LOGGER.info('WORK %s', _work.path)
        _work.save(force=True)
        assert not _ety_c.find_outputs()
        _work_c = pipe.CACHE.obt_work(_work)

        # Test publish without PiniHelper
        _LOGGER.info(' - CUR WORK OUTS %s', _work_c.find_outputs())
        if _work_c.outputs:
            _work_c.find_outputs(force=True)
        _LOGGER.info(' - WORK C OUTS %s', _work_c.find_outputs())
        assert not _work_c.find_outputs()
        assert not _work_c.outputs
        _outs = _handler.publish(force=True, version_up=False)
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
        _next = pipe.version_up()
        assert isinstance(_next, pipe.CPWork)
        assert not isinstance(_next, cache.CCPWork)
        assert pipe.CACHE.cur_work
        assert pipe.CACHE.cur_work.ver_n == 2
        _work_c = pipe.CACHE.obt_work(_next)

        # Test publish with PiniHelper
        _helper = helper.obt_helper()
        _helper.jump_to(_work_c)
        assert _helper.work.exists()
        assert _helper.work == pipe.cur_work()
        assert _helper.entity is pipe.CACHE.cur_entity
        assert _helper.work_dir is pipe.CACHE.cur_work_dir
        assert _helper.work is pipe.CACHE.cur_work

        # Publish
        _helper.ui.MainPane.select_tab('Export')
        _pub = _helper.ui.EPublishHandler.selected_data()
        _pub.ui.VersionUp.setChecked(False)
        _pub.ui.ExportFbx.setChecked(False)
        _helper.ui.MainPane.select_tab('Export')
        _helper.ui.EExportPane.select_tab('Publish')
        _out = single(_helper._callback__EPublish(force=True))
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
        _helper.ui.WWorks.select_data(_helper.next_work)
        _helper.ui.WSave.click()
        assert pipe.CACHE.cur_work.ver_n == 3
        assert not error.TRIGGERED
