import unittest

from pini import dcc


class TestDCC(unittest.TestCase):

    def test_scene_data(self):
        if dcc.NAME == 'maya':
            for _data in [True, False, 1, 'Hello!', 1.0]:
                dcc.set_scene_data('Test', _data)
                assert dcc.get_scene_data('Test') == _data
