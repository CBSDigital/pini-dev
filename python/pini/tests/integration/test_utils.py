import logging
import random
import time
import unittest

from pini.utils import cache

_LOGGER = logging.getLogger(__name__)


class TestCache(unittest.TestCase):

    def test_max_ages(self):

        class _Blah:

            @property
            def cache_fmt(self):
                return '~/tmp/cache/test_{func}.pkl'

            @cache.get_method_to_file_cacher(max_age=1)
            def rand(self):
                return random.random()

        _blah = _Blah()
        _results = set()
        for _ in range(10):
            _result = _blah.rand()
            _results.add(_result)
            _LOGGER.info(_result)
            time.sleep(0.19)
        assert len(_results) == 2
