import logging
import unittest

from pini import testing, dcc
from pini.tools import helper
from pini.utils import assert_eq

_LOGGER = logging.getLogger(__name__)


class TestHelper(unittest.TestCase):

    def test_output_to_namespace(self):

        dcc.new_scene(force=True)

        _cam_abc = testing.TEST_SHOT.to_output(
            'cache', output_type='cam', extn='abc', output_name='blah',
            ver_n=1, task='anim')
        _cam_ns = helper.output_to_namespace(_cam_abc)
        _LOGGER.info('CAM NS %s', _cam_ns)
        assert _cam_ns == 'blah'

        _char_abc = testing.TEST_SHOT.to_output(
            'cache', output_type='char', extn='abc', output_name='blue',
            ver_n=1, task='anim')
        assert helper.output_to_namespace(_char_abc) == 'blue'
        _char_pub = testing.TEST_ASSET.to_output(
            'publish', extn='ma', task='rig')
        _char_ns = helper.output_to_namespace(_char_pub)
        _LOGGER.info(_char_ns)
        assert_eq(_char_ns, 'test01')

        _rest_cache = testing.TEST_ASSET.to_output(
            'cache', extn='abc', output_name='restCache',
            task='rig', ver_n=1, output_type='geo')
        assert helper.output_to_namespace(_rest_cache) == 'test01'
