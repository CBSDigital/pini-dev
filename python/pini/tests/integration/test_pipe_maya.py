import logging
import unittest

from pini import testing, pipe
from pini.utils import assert_eq

_LOGGER = logging.getLogger()


class TestCache(unittest.TestCase):

    def test_publish_cache(self):

        _ety = pipe.CACHE.obt(testing.TEST_ASSET)

        print(_ety.cache_fmt)
        _ety.find_publishes(force=True)
        assert _ety.find_publishes()
        assert _ety.find_publishes(ver_n='latest')

        _job = pipe.CACHE.obt(testing.TEST_JOB)
        _job.find_publishes(force=True)
        assert _job.find_publishes()
        assert _job.find_publishes(task='model', ver_n='latest', versionless=False)

        _work = _ety.to_work(task='model')
        _pub_g = _ety.find_publish(
            task='model', tag=_work.tag, ver_n='latest', versionless=False,
            type_='publish')
        _pub_c = pipe.CACHE.obt(_pub_g)
        assert_eq(_pub_g.path, _pub_c.path)
        assert_eq(_pub_c._latest, _pub_g.latest)
