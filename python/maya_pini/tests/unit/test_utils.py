import unittest

from maya_pini.utils import to_clean, to_namespace


class TestUtils(unittest.TestCase):

    def test(self):

        assert to_clean('a:b:c') == 'c'

    def test_to_namespace(self):

        assert not to_namespace("A")
        assert to_namespace("A:B") == 'A'
        assert to_namespace("A:B:C") == 'A:B'
