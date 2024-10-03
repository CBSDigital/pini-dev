import importlib
import logging
import unittest

import pini

from pini.tools import usage, error, pyui
from pini.utils import File, PyFile, assert_eq

_LOGGER = logging.getLogger(__name__)
_DIR = File(__file__).to_dir()
_TEST_PY = _DIR.to_file('_pyui_test.py')

_TRACKBACK_STRS = [
r'''
Traceback (most recent call last):
  File "C:\Users\ninhe\dev\pini-dev\python\maya_pini\tests\integration\test_open_maya.py", line 53, in test_basic_node_relationships
    asdasdas
NameError: name 'asdasdas' is not defined
''',  # nopep8

r'''
Traceback (most recent call last):
  File "C:\Users/hvanderbeek/dev/pini-dev/python\pini\tests\unit\test_pipe.py", line 308, in test_update_publish_cache
    assert _shot.find_publishes()
AssertionError
''',

]


class TestErrorCatcher(unittest.TestCase):

    def test_error_from_str(self):

        for _tb in _TRACKBACK_STRS:
            error.error_from_str(_tb)


class TestPyui(unittest.TestCase):

    def test_read_py_file_qt(self):

        _LOGGER.info('TEST PYUI')

        _mod = PyFile(_TEST_PY).to_module()
        _LOGGER.info(' - MOD %s', _mod)
        importlib.reload(_mod)
        _LOGGER.info(' - RELOADED')
        assert isinstance(_mod.print_something, pyui.PUDef)

        _ui = pyui.build(_TEST_PY, mode='qt', load_settings=False)
        _LOGGER.info(' - UI %s', _ui)
        _ui.hide()
        _ui.close()

    def test_qt_y_offset(self):

        _ui = pyui.build(_TEST_PY, mode='qt', load_settings=False)
        _pos_y = _ui.pos().y()
        assert_eq(_ui.read_settings()['geometry']['y'], _pos_y)
        _LOGGER.info('RELAUNCHING')
        _ui = pyui.build(_TEST_PY, mode='qt', load_settings=True)
        assert_eq(_ui.pos().y(), _pos_y)
        assert_eq(_ui.read_settings()['geometry']['y'], _pos_y)

        _ui = pyui.build(_TEST_PY, mode='qt', load_settings=True)
        _ui.def_btns['Test'].click()
        assert_eq(_ui.pos().y(), _pos_y)
        assert_eq(_ui.read_settings()['geometry']['y'], _pos_y)

        _ui = pyui.build(_TEST_PY, mode='qt', load_settings=True)
        assert_eq(_ui.pos().y(), _pos_y)
        assert_eq(_ui.read_settings()['geometry']['y'], _pos_y)
        _ui.hide()
        _ui.close()


class TestRelease(unittest.TestCase):

    def test_usage(self):

        assert usage._read_mod_ver(pini, force=True)
