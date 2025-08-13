import logging
import unittest

from pini import dcc

_LOGGER = logging.getLogger(__name__)


class TestDCC(unittest.TestCase):

    def test_scene_data(self):
        for _data in [
                True,
                False,
                1,
                'Hello!',
                1.0,
                ['A', 'B'],
        ]:
            _LOGGER.info(' - DATA %s', _data)
            dcc.set_scene_data('Test', _data)
            assert dcc.get_scene_data('Test') == _data
