import logging
import unittest

import pini

from pini.tools import usage

_LOGGER = logging.getLogger(__name__)


class TestRelease(unittest.TestCase):

    def test_usage(self):

        assert usage._read_mod_ver(pini, force=True)
