import logging
import unittest

import pini

from pini.tools import usage, error

_LOGGER = logging.getLogger(__name__)

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


class TestRelease(unittest.TestCase):

    def test_usage(self):

        assert usage._read_mod_ver(pini, force=True)
