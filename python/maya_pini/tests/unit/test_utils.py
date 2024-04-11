import unittest

from maya_pini.utils import to_clean, to_namespace, apply_namespace


class TestUtils(unittest.TestCase):

    def test_apply_namespace(self):

        assert apply_namespace('test:blah.f[0]') == 'blah.f[0]'
        assert apply_namespace('test:blah.f[0]', '') == 'blah.f[0]'
        assert apply_namespace('test:blah.f[0]', None) == 'blah.f[0]'
        assert apply_namespace('test:blah.f[0]', 'test') == 'test:blah.f[0]'
        assert apply_namespace('test:blah') == 'blah'

    def test_to_clean(self):
        assert to_clean('a:b:c') == 'c'

    def test_to_namespace(self):

        assert not to_namespace("A")
        assert to_namespace("A:B") == 'A'
        assert to_namespace("A:B:C") == 'A:B'
