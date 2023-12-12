import os
import unittest

from pini.tools import release


class TestRelease(unittest.TestCase):

    def test_repo(self):

        _path = '{}/pini-dev'.format(os.environ['DEV'])
        _repo = release.PRRepo(_path)
        print(_repo)
        print(_repo.read_version())
        print(_repo.version)

    def test_version(self):

        _ver = release.PRVersion('1.2.3')
        assert _ver.to_next('major').string == '2.0.0'
        assert _ver.to_next('minor').string == '1.3.0'
        assert _ver.to_next('patch').string == '1.2.4'
        assert _ver == release.PRVersion('1.2.3')
