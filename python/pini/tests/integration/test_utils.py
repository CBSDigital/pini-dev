import logging
import random
import time
import unittest

from pini import icons
from pini.utils import cache, Image, Res, TMP

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


class TestImage(unittest.TestCase):

    def test_resize_exr(self):

        _img = Image(icons.find('Green Apple'))
        _LOGGER.info(' - RES %s', _img.to_res())
        assert _img.to_res() == Res(144, 144)
        _exr = Image(TMP.to_file('pini/test.exr'))
        _exr.delete(force=True)
        assert not _exr.exists()
        _img.convert(_exr, size=Res(50, 50))
        assert _exr.exists()
        _LOGGER.info(' - EXR %s', _exr.to_res())
        assert _exr.to_res() == Res(50, 50)
