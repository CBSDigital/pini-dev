import logging
import pprint
import unittest

from pini import testing, dcc
from pini.tools import helper, pyui
from pini.utils import assert_eq, File, PyFile, six_reload

_LOGGER = logging.getLogger(__name__)
_DIR = File(__file__).to_dir()
_TEST_PY = _DIR.to_file('_pyui_test.py')


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


class TestPyui(unittest.TestCase):

    def test_read_py_file(self):

        _LOGGER.info('TEST PYUI')

        _mod = PyFile(_TEST_PY).to_module()
        _LOGGER.info(' - MOD %s', _mod)
        six_reload(_mod)
        _LOGGER.info(' - RELOADED')
        assert isinstance(_mod.print_something, pyui.PUDef)

        _pyui = pyui.PUFile(_TEST_PY)
        _LOGGER.info(' - PYUI %s', _pyui)
        pprint.pprint([(_elem, _elem.name) for _elem in _pyui.find_ui_elems()])
        _section = _pyui.find_ui_elem('Create')
        _LOGGER.info(' - SECTION %s', _section)
        assert _section.collapse
        assert not _pyui.find_ui_elem('Dev').collapse
