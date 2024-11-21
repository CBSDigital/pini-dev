import logging
import unittest

from pini import dcc, pipe, testing
from pini.tools import helper
from pini.pipe import cache
from pini.utils import TMP_PATH, Dir

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

        _LOGGER.info('TEST PUBLISH')

        dcc.new_scene(force=True)

        # Flush tmp asset
        _tmp_asset_c = pipe.CACHE.obt(testing.TMP_ASSET)
        assert _tmp_asset_c is pipe.CACHE.obt(testing.TMP_ASSET)
        _tmp_asset_c.flush(force=True)
        assert not _tmp_asset_c.outputs
        assert _tmp_asset_c is pipe.CACHE.obt(testing.TMP_ASSET)
        assert not pipe.CACHE.obt(testing.TMP_ASSET).outputs
        assert not pipe.CACHE.obt(testing.TEST_JOB).find_publishes(asset='tmp')
        _LOGGER.info(' - FLUSHED TMP ASSET')
        print()

        # Check job + entity objects
        _job_c = pipe.CACHE.obt_job(testing.TEST_JOB)
        _LOGGER.info(' - JOB C %s', _job_c)
        assert isinstance(_job_c, cache.CCPJob)
        assert _job_c.exists()
        assert _job_c in pipe.CACHE.jobs
        assert _job_c is pipe.CACHE.obt_job(_job_c)
        _ety_c = pipe.CACHE.obt(testing.TMP_ASSET)
        _LOGGER.info(' - ETY C (A) %s', _ety_c)
        _LOGGER.info(' - OUTS %s', _ety_c.find_outputs())
        assert not _ety_c.find_outputs()
        assert isinstance(_ety_c, pipe.CPAsset)
        assert isinstance(_ety_c, cache.CCPEntity)

        # Check work_dir + work objects
        _work_dir_c = _ety_c.to_work_dir(task='rig')
        assert not _work_dir_c.exists()
        _LOGGER.info('SET UP WORK DIR %s', _work_dir_c)
        assert isinstance(_work_dir_c, cache.CCPWorkDir)
        assert _work_dir_c.entity == _ety_c
        assert _work_dir_c.entity is _ety_c
        _work_1 = _ety_c.to_work(task='rig', tag='PublishTest')
        _LOGGER.info('WORK 1 %s', _work_1)
        assert _work_1
        assert _work_1.job is _job_c
        assert isinstance(_work_1, cache.CCPWork)
        assert isinstance(_work_1.work_dir, cache.CCPWorkDir)
        assert _work_1.entity is _ety_c
        assert not pipe.CACHE.cur_work
        assert _work_1 not in _work_dir_c.works
        assert not _work_dir_c.works
        print('')

        # Test create work object
        _LOGGER.info('TESTING SAVE WORK')
        dcc.new_scene(force=True)
        _helper = helper.obt_helper(reset_cache=False)
        assert _work_1.job is _job_c
        _work_1.save(force=True)
        _work_1 = pipe.CACHE.obt_work(_work_1, catch=False)
        assert _work_1
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

        # Test object integrity
        assert _work_1 in _work_dir_c.works
        assert pipe.CACHE.obt_work_dir(_work_dir_c)
        assert pipe.CACHE.obt_work(_work_1)
        assert pipe.CACHE.obt_job(_work_1.job)
        assert pipe.CACHE.cur_job
        assert pipe.CACHE.cur_entity
        assert pipe.CACHE.cur_work_dir
        assert pipe.CACHE.cur_work
        assert not _work_1.find_outputs()
        print('')

        # Test publish
        _LOGGER.info('TESTING PUBLISH')
        _basic_pub = dcc.find_export_handler('BasicPublish', catch=True)
        if not _basic_pub:
            assert dcc.NAME in ['hou', 'nuke']
        else:
            _helper.ui.MainPane.select_tab(_helper.ui.ExportTab)
            assert _work_1.job is _job_c
            assert _work_1.job is pipe.CACHE.cur_job
            _basic_pub.publish(work=_work_1, force=True, version_up=False)
            assert pipe.CACHE.obt(testing.TEST_JOB).find_publishes(asset='tmp')
