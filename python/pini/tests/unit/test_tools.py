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

r'''
Traceback (most recent call last):
  File "C:\Users\hvanderbeek\dev\pini-dev\python\maya_pini\open_maya\wrapper\pom_mesh.py", line 32, in __init__
    om.MFnMesh.__init__(self, _m_dag)
ValueError: object is incompatible with MFnMesh constructor

The above exception was the direct cause of the following exception:

Traceback (most recent call last):
  File "C:\Users\hvanderbeek\dev\pini-dev\python\maya_pini\utils\mu_dec.py", line 56, in _ns_clean_fn
    _result = func(*args, **kwargs)
  File "C:\Users\hvanderbeek\dev\pini-dev\python\maya_pini\tests\integration\test_open_maya.py", line 62, in test_camera
    _sphere = pom.CMDS.polySphere()
  File "C:\Users\hvanderbeek\dev\pini-dev\python\maya_pini\open_maya\pom_cmds.py", line 133, in _map_results_func
    _result = pom.CMesh(_tfm)
  File "C:\Users\hvanderbeek\dev\pini-dev\python\maya_pini\open_maya\wrapper\pom_mesh.py", line 35, in __init__
    raise ValueError(
ValueError: Failed to construct MFnMesh object tmp:pSphere1
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
        _ui.delete()

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
        _ui.delete()


class TestRelease(unittest.TestCase):

    def test_usage(self):

        assert usage._read_mod_ver(pini, force=True)
