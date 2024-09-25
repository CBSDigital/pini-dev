import unittest

from pini import testing, pipe, dcc, qt
from pini.tools import error
from pini.utils import assert_eq


class TestCache(unittest.TestCase):

    def test_cache_update_on_save(self):

        assert not error.TRIGGERED

        _shot = testing.TEST_SHOT
        _shot_c = pipe.CACHE.obt(_shot)
        _work_dir_c = _shot_c.find_work_dir(task='anim', dcc_=dcc.NAME)

        _work_a1 = _work_dir_c.to_work()

        # Reset
        for _o_work in _work_a1.work_dir.find_works():
            if _o_work.tag and 'tmp' not in _o_work.tag:
                continue
            _o_work.delete(force=True)
        dcc.new_scene(force=True)
        _work_a1.save(force=True)

        _work_a1_c = pipe.CACHE.cur_work
        assert isinstance(_work_a1_c.work_dir, pipe.CPWorkDir)
        _work_dir_c = pipe.CACHE.obt_work_dir(_work_a1_c.work_dir)
        assert _work_a1_c.work_dir is _work_dir_c
        assert _work_dir_c is pipe.CACHE.obt_work_dir(_work_dir_c.path)
        assert _work_dir_c is pipe.CACHE.cur_work_dir
        assert _work_a1_c is pipe.CACHE.cur_work

        _work_b1_c = _work_dir_c.to_work(tag='tmpB')
        _work_b1_c = _work_b1_c.save(force=True)
        assert _work_a1_c.work_dir is _work_dir_c
        assert _work_b1_c.work_dir is _work_dir_c
        assert _work_dir_c is pipe.CACHE.cur_work_dir
        assert _work_b1_c == pipe.CACHE.cur_work
        assert _work_b1_c is pipe.CACHE.cur_work

        assert not error.TRIGGERED

    def test_publish_cache(self):

        testing.check_test_asset()

        _ety = pipe.CACHE.obt(testing.TEST_ASSET)

        print(_ety.cache_fmt)
        _ety.find_publishes(force=True)
        assert _ety.find_publishes()
        assert _ety.find_publishes(ver_n='latest')

        _job = pipe.CACHE.obt(testing.TEST_JOB)
        _job.find_publishes(force=True)
        assert _job.find_publishes()
        assert _job.find_publishes(task='model', ver_n='latest', versionless=False)

        _pub_g = _ety.find_publish(
            task='model', tag=pipe.DEFAULT_TAG, ver_n='latest', versionless=False,
            type_='publish')
        _pub_c = pipe.CACHE.obt(_pub_g)
        assert_eq(_pub_g.path, _pub_c.path)
        assert_eq(_pub_c._latest, _pub_g.latest)

    def test_read_publishes(self):

        for _job in qt.progress_bar(pipe.CACHE.jobs, 'Checking {:d} job{}'):
            _pubs = _job.find_publishes()
            print(_job, len(_pubs))
            for _pub in _pubs:
                assert not _pub.shot
                assert not _pub.sequence
