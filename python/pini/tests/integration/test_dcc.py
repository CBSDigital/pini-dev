import logging
import unittest

from pini import dcc, pipe, testing
from pini.tools import helper, error
from pini.pipe import cache
from pini.utils import TMP_PATH, Dir, single

_LOGGER = logging.getLogger(__name__)


class TestDCC(unittest.TestCase):

    def test_cur_scene(self):
        dcc.new_scene(force=True)
        assert not dcc.cur_file()
        assert not pipe.cur_work()
        assert not dcc.unsaved_changes()

    def test_force_save(self):
        dcc.new_scene(force=True)
        try:
            dcc._force_save()
        except RuntimeError:
            pass
        else:
            raise AssertionError
        _tmp = Dir(TMP_PATH).to_file('tmp.mb')
        dcc.save(_tmp, force=True)
        dcc._force_save()


class TestPublish(unittest.TestCase):

    def test_publish(self):

        dcc.new_scene(force=True)

        _job_c = pipe.CACHE.obt_job(testing.TEST_JOB)
        assert isinstance(_job_c, cache.CCPJob)
        assert _job_c.exists()
        assert _job_c in pipe.CACHE.jobs
        assert _job_c is pipe.CACHE.obt_job(_job_c)
        _ety_c = pipe.CACHE.obt(testing.TMP_ASSET)
        if not _ety_c.exists():
            _ety_c.create(force=True)
        _ety_c.flush(force=True)
        _LOGGER.info('ETY C (A) %s', _ety_c)
        pipe.CACHE.reset()
        assert not _ety_c.find_outputs()

        # Rebuild job/shot after reset
        _job_c = pipe.CACHE.obt_job(testing.TEST_JOB)
        _LOGGER.info('ETY C (B) %s', _ety_c)
        assert isinstance(_ety_c, pipe.CPAsset)
        _ety_c = pipe.CACHE.obt_entity(_ety_c)
        _LOGGER.info('ETY C (C) %s', _ety_c)
        assert isinstance(_ety_c, cache.CCPEntity)

        # Test create work object
        _work_dir_c = _ety_c.to_work_dir(task='rig')
        assert not _work_dir_c.exists()
        _LOGGER.info('SET UP WORK DIR %s', _work_dir_c)
        assert isinstance(_work_dir_c, cache.CCPWorkDir)
        assert _work_dir_c.entity is _ety_c
        _work_1 = _ety_c.to_work(task='rig', tag='PublishTest')
        _LOGGER.info('WORK 1 %s', _work_1)
        assert isinstance(_work_1, cache.CCPWork)
        assert isinstance(_work_1.work_dir, cache.CCPWorkDir)
        assert _work_1.entity is _ety_c
        assert not pipe.CACHE.cur_work
        assert _work_1 not in _work_dir_c.works

        # Test save
        _work_1.save(force=True)
        _work_1 = pipe.CACHE.obt_work(_work_1)
        _ety_c = pipe.CACHE.obt_entity(_work_1.entity)
        assert _work_1.entity == _job_c.obt_entity(_work_1.entity)
        _LOGGER.info('CUR ETY %s', pipe.CACHE.cur_entity)
        _LOGGER.info('WORK 1 ETY %s', _work_1.entity)
        _LOGGER.info('JOB FIND ETY %s', _job_c.obt_entity(_work_1.entity))
        assert _work_1.entity is _job_c.obt_entity(_work_1.entity)
        _work_dir_c = _ety_c.obt_work_dir(_work_1.work_dir)
        assert _work_dir_c is _ety_c.obt_work_dir(_work_1.work_dir)
        assert _work_dir_c is _ety_c.to_work_dir(task='rig', dcc_=dcc.NAME)
        assert _work_dir_c == _work_1.work_dir
        assert _work_dir_c is _work_1.work_dir
        _LOGGER.info('WORK DIR C %s %s', _work_dir_c, _ety_c.work_dirs)
        _work_dir_c = _ety_c.to_work_dir(task='rig', dcc_=dcc.NAME)
        assert _work_dir_c == _work_1.work_dir
        assert _work_dir_c is _work_1.work_dir

        assert _work_1 in _work_dir_c.works
        assert pipe.CACHE.obt_work_dir(_work_dir_c)
        assert pipe.CACHE.obt_work(_work_1)
        assert pipe.CACHE.obt_job(_work_1.job)
        assert pipe.CACHE.cur_job
        assert pipe.CACHE.cur_entity
        assert pipe.CACHE.cur_work_dir
        assert pipe.CACHE.cur_work
        assert not _work_1.find_outputs()

        # Test publish
        _basic_pub = dcc.find_export_handler(
            'publish', filter_='Basic', catch=True)
        if not _basic_pub:
            assert dcc.NAME in ['hou', 'nuke']
        else:
            _basic_pub.publish(work=_work_1, force=True, version_up=False)

    def test_version_up_publish(self):

        assert not error.TRIGGERED
        testing.TMP_ASSET.flush(force=True)
        pipe.CACHE.reset()

        _handler = dcc.find_export_handler(
            'publish', filter_='basic', catch=True)
        if not _handler:
            assert dcc.NAME in ['hou', 'nuke']
            return

        # Save basic scene to publish
        dcc.new_scene(force=True)
        if dcc.NAME == 'maya':
            from maya import cmds
            cmds.polyCube()
        elif dcc.NAME == 'nuke':
            import nuke
            nuke.createNode('Constant')
        else:
            raise ValueError
        _work = testing.TMP_ASSET.to_work(task='mod')
        _LOGGER.info('WORK %s', _work.path)
        _work.save(force=True)
        assert not _work.find_outputs()
        _work_c = pipe.CACHE.obt_work(_work)

        # Test publish without PiniHelper
        _LOGGER.info(' - CUR WORK OUTS %s', pipe.cur_work().find_outputs())
        assert not pipe.cur_work().find_outputs()
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
        assert pipe.CACHE.cur_work
        assert pipe.CACHE.cur_work.ver_n == 2
        _work_c = pipe.CACHE.obt_work(_next)

        # Test publish with PiniHelper
        _helper = helper.DIALOG
        if not helper.is_active():
            _helper = helper.launch()
        else:
            _helper._callback__Refresh()
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
        _helper._callback__WSave()
        assert pipe.CACHE.cur_work.ver_n == 3
        assert not error.TRIGGERED
