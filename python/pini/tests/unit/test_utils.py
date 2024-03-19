import getpass
import os
import logging
import pprint
import platform
import random
import unittest

from pini import testing, icons
from pini.tools import release
from pini.utils import (
    Path, File, Dir, assert_eq, abs_path, norm_path, HOME_PATH, str_to_ints,
    TMP_PATH, single, find, passes_filter, Seq, cache_result, path, to_nice,
    get_method_to_file_cacher, ints_to_str, str_to_seed, clip, find_exe,
    merge_dicts, to_snake, strftime, to_ord, to_camel, PyFile, EMPTY,
    file_to_seq, split_base_index, nice_age, find_viewers, to_pascal,
    Image, TMP)
from pini.utils.u_mel_file import _MelExpr

_LOGGER = logging.getLogger(__name__)


class TestUtils(unittest.TestCase):

    def test_filter(self):

        assert passes_filter('C:/tmp/test2.txt', '')
        assert passes_filter('C:/tmp/test2.txt', 'test2')
        assert not passes_filter('C:/tmp/test.txt', 'test2')
        assert passes_filter('C:/tmp/test.txt', 'test2 test')
        assert not passes_filter('C:/tmp/test.txt', '+test2 test')
        assert not passes_filter('C:/tmp/test.txt', '-test')
        assert passes_filter('C:/tmp/test.txt', '-test3')

    def test_find_exe(self):

        assert find_exe('ffmpeg')
        # assert find_exe('maya')
        # assert find_exe('mayapy')

    def test_find_viewers(self):
        assert find_viewers()

    def test_ints_to_str(self):
        assert_eq(ints_to_str([1, 2, 3, 10, 11, 12]), '1-3,10-12')
        assert_eq(ints_to_str([1, 2, 3]), '1-3')
        assert_eq(ints_to_str([-1, 0, 1, 2, 3]), '-1-3')
        assert_eq(ints_to_str([1, 2]), '1-2')
        assert_eq(ints_to_str([-1, 2, 3]), '-1,2-3')

    def test_mel_file(self):

        _text = '''shelfButton -command "/*\n======\n===\n\n     bhGhost 1.32 - - bug fix for crashing issue with 'Create Trackers' function in Maya 2017/2018\n\t \n\t \n\t \n     \n     - added option to ghost bh Multiples automatically if they are in the scene\n     \n\t 140616 _ added check for existing 'hide on playback' layer so that checkbox in UI is updated to" -blah'''

        _text = '''shelfButton -command "bhGhost 1.32 - -"'''
        _expr = _MelExpr(_text)
        assert _expr.read_flag('command') == "bhGhost 1.32 - -"

        _text = '''shelfButton -command "bhGhost 1.32 - -" -blah 1'''
        _expr = _MelExpr(_text)
        assert _expr.read_flag('command') == "bhGhost 1.32 - -"
        assert _expr.read_flag('blah') == '1'

        _text = '''shelfButton -command "/*\n======\n===\n\n     bhGhost 1.32 - - bug fix for crashing issue with 'Create Trackers' function in Maya 2017/2018\n\t \n\t \n\t \n     \n     - added option to ghost bh Multiples automatically if they are in the scene\n     \n\t 140616 _ added check for existing 'hide on playback' layer so that checkbox in UI is updated to"'''
        _expr = _MelExpr(_text)
        assert _expr.read_flag('command').endswith('updated to')

    def test_merge_dicts(self):

        _a = {'AList': [1, 2, 3],
              'ADict': {'A': 1}}
        _b = {'BList': [1, 2, 3]}
        _r = merge_dicts(_a, _b)
        _a['AList'].append(4)
        _a['ADict']['B'] = 2
        _b['BList'].append(4)
        assert len(_r['AList']) == 3
        assert len(_r['BList']) == 3
        assert len(_r['ADict']) == 1

    def test_method_to_file_cacher(self):

        class _Test(object):

            cache_fmt = Dir(TMP_PATH).to_file('{func}.yml').path

            @get_method_to_file_cacher(mtime_outdates=False)
            def rand(self):
                return random.random()

        _test = _Test()
        _cache = File(_test.cache_fmt.format(func='rand'))
        _cache.delete(force=True)
        _rand = _test.rand()
        assert _rand == _test.rand()
        assert _cache.exists()
        _cache.delete(force=True)
        assert _rand == _test.rand()

    def test_split_base_index(self):
        assert split_base_index('test001') == ('test', 1)
        assert split_base_index('test001a') == ('test001a', 0)
        assert split_base_index('blah67') == ('blah', 67)

    def test_nice_age(self):
        assert nice_age(60*60+1, pad=2) == '01h00m01s'
        assert nice_age(24*60*60+1, pad=2, depth=2) == '01d00h'

    def test_strftime(self):
        assert strftime('%d/%m/%y %D', 1663021730) in [
            '12/09/22 12th',  # LAX
            '13/09/22 13th',  # CPH
        ]

    def test_str_to_ints(self):
        assert str_to_ints('90,100-200', inc=10) == [90, 100, 110, 120, 130, 140, 150, 160, 170, 180, 190, 200]
        assert str_to_ints('10,') == [10]

    def test_str_to_seed(self):
        assert isinstance(str_to_seed('blah'), random.Random)
        assert str_to_seed('blah').random() == str_to_seed('blah').random()
        assert str_to_seed('blah').random() != str_to_seed('blahasda').random()

    def test_to_camel(self):
        assert_eq(to_camel('cat_ginger_A'), 'catGingerA')
        assert_eq(to_camel('This Is Some Text'), 'thisIsSomeText')
        assert_eq(to_camel('this_is_some_text'), 'thisIsSomeText')

    def test_to_nice(self):
        assert to_nice('_CleanBadSceneNodes') == 'clean bad scene nodes'

    def test_to_ord(self):
        assert_eq(to_ord(0), 'th')
        assert_eq(to_ord(1), 'st')
        assert_eq(to_ord(2), 'nd')
        assert_eq(to_ord(3), 'rd')
        assert_eq(to_ord(4), 'th')
        assert_eq(to_ord(10), 'th')
        assert_eq(to_ord(11), 'th')
        assert_eq(to_ord(13), 'th')

    def test_to_pascal(self):

        _str = 'aasdas - asdadd - asdss'
        assert to_pascal(_str) == 'AasdasAsdaddAsdss'

    def test_to_snake(self):
        assert_eq(to_snake('a test'), 'a_test')
        assert_eq(to_snake('MyTest'), 'my_test')
        assert_eq(to_snake('My  Test'), 'my_test')


class TestCache(unittest.TestCase):

    def test_cache_result(self):

        @cache_result
        def _test(aaa, bbb, ccc=1, ddd=True, force=True):
            return random.random()

        _result = _test(1, 2)
        print(_result)
        print(_test(1, 2))
        assert _test(1, 2) == _result
        assert _test(1, 2, ddd=False) != _result
        assert _test(1, 2) == _test(1, 2)
        assert _test(1, 2) != _test(1, 2, force=True)

        class _Test(object):

            @cache_result
            def func(self):
                return random.random()

            @cache_result
            def func_2(self, aaa=1):
                return random.random()

            def func_3(self):
                return random.random()

        _test = _Test()
        assert _test.func() == _test.func()
        assert _test.func_2() == _test.func_2()
        assert _test.func_2(20) == _test.func_2(20)
        assert _test.func_2() != _test.func_2(20)

        class _Test2(_Test):

            @cache_result
            def func_3(self):
                return super(_Test2, self).func_3()

        _test_2 = _Test2()
        print(_test_2.func_3())
        print(_test_2.func_3())


class TestPath(unittest.TestCase):

    def test(self):

        _LOGGER.info('TMP DIR %s', TMP_PATH)
        _user = getpass.getuser()
        _tmp_fmts = [
            'C:/users/{}/appdata/local/temp'.format(_user),
            'C:/Users/{}~1/AppData/Local/Temp'.format(_user[:6].upper()),
            'C:/Users/{}/AppData/Local/Temp'.format(_user),
            '/usr/tmp',
            '/tmp',
        ]
        for _tmp_fmt in _tmp_fmts:
            if TMP_PATH.startswith(_tmp_fmt):
                break
        else:
            raise RuntimeError("Bad TMP_PATH "+TMP_PATH)
        assert File('/tmp/test').extn is None
        if platform.system() == 'Windows':
            assert not Dir('D:/').to_dir()
        assert Dir('V:/').rel_path('V:/Jobs') == 'Jobs'

        # Test hash
        _path_a = Path('A:/test')
        _path_b = Path('A:/test')
        _paths = {_path_a}
        assert len(_paths) == 1
        _paths.add(_path_b)
        assert len(_paths) == 1

        # Test is abs
        _dir = path.Dir('./')
        assert not _dir.is_abs()
        _dir = path.Dir('V:/blah')
        assert _dir.is_abs()

        # Test to abs
        _root = 'P:/blah'
        assert path.Dir('V:/test').to_abs(root=_root).path == 'V:/test'
        assert path.Dir('test').to_abs(root=_root).path == 'P:/blah/test'

    def test_abs_path(self):

        try:
            abs_path(None)
        except ValueError:
            pass
        else:
            raise AssertionError

        os.chdir(Path('~').path)
        assert_eq(abs_path('./test.txt'), HOME_PATH+'/test.txt')
        assert_eq(abs_path('./test.txt', root='C:/Users'),
                  'C:/Users/test.txt')
        assert_eq(abs_path('../test.txt', root='C:/Users'),
                  'C:/test.txt')

        _path = abs_path('~/dev/pini-legacy/python')
        assert _path == HOME_PATH+'/dev/pini-legacy/python'

        assert_eq(abs_path('/tmp'), '/tmp')

        assert abs_path('P:pipeline') == 'P:/pipeline'
        assert abs_path('file:///mnt/jobs') == '/mnt/jobs'

    def test_bkp_file(self):

        _file = TMP.to_file('test/.minttyrc')
        _file.delete(force=True)
        assert not _file.extn
        assert not _file.to_file().extn
        _file.touch()
        _file.bkp()
        assert _file.find_bkps()

    def test_find(self):

        # Test find in test dir
        _tmp_path = norm_path(TMP_PATH+'/test')
        print('TMP', _tmp_path, abs_path(_tmp_path))
        _tmp_dir = Dir(_tmp_path)
        print('TMP', _tmp_dir)
        _tmp_dir.delete(force=True)
        _tmp_dir.mkdir()
        for _path in ['dir/test.txt',
                      'dir/test2.txt',
                      'dir/.test2.txt',
                      '.hidden/test.txt',
                      'test.file']:
            _file = _tmp_dir.to_file(_path)
            _file.touch()
            assert _file.exists()
        assert _tmp_dir.exists()
        _files = find(_tmp_dir, type_='f')
        assert len(_files) == 3
        assert isinstance(_files[0], str)
        _files = _tmp_dir.find(type_='f')
        assert len(_files) == 3
        _files = _tmp_dir.find(type_='f', hidden=True)
        assert len(_files) == 5
        _files = _tmp_dir.find(type_='f', hidden=True, extn='txt')
        assert len(_files) == 4
        _file = single(_tmp_dir.find(type_='f', base='test2', class_=True))
        assert _file.extn == 'txt'
        assert _file.base == 'test2'
        # asdasd
        _files = _tmp_dir.find(type_='d')
        assert len(_files) == 1
        _files = _tmp_dir.find()
        assert len(_files) == 4
        pprint.pprint(_files)
        _files = _tmp_dir.find(type_='f', depth=1)
        assert len(_files) == 1
        _files = _tmp_dir.find(type_='d', class_=True)
        assert len(_files) == 1
        _dir = single(_files)
        _LOGGER.info('DIR %s', _dir)
        _LOGGER.info('TMP DIR %s', TMP_PATH)
        assert _dir.path.startswith(TMP_PATH)
        assert _tmp_dir.rel_path(_dir) == 'dir'
        _file = single(_tmp_dir.find(
            full_path=False, class_=str, filter_='test2'))
        assert _file.count('/') == 1

        # Test using test dir missing
        _tmp_dir.delete(force=True)
        try:
            _tmp_dir.find()
        except OSError:
            pass
        else:
            raise AssertionError
        assert not _tmp_dir.find(catch_missing=True)
        assert isinstance(_tmp_dir.find(catch_missing=True), list)

    def test_matches(self):

        # Test matches
        _file_a = Dir(TMP_PATH).to_file('test_a.txt')
        _file_a.write('AAA\nBBB\nCCC', force=True)
        assert _file_a.exists()
        _file_b = Dir(TMP_PATH).to_file('test_b.txt')
        _file_b.write('AAA\nBBB\nDDD', force=True)
        assert _file_b.exists()
        _file_c = Dir(TMP_PATH).to_file('test_c.txt')
        _file_c.write('AAA\nBBB\nCCC', force=True)
        assert _file_c.exists()

    def test_norm_path(self):

        # Test norm path
        _path = 'c:\\test'
        assert_eq(norm_path(_path), 'C:/test')
        _path = '/c/test'
        assert_eq(norm_path(_path), 'C:/test')
        _path = r'c:\users\hvande~1'
        assert_eq(norm_path(_path), 'C:/users/hvande~1')

    def test_path(self):

        # Test path object
        _path = 'C:\\test'
        assert Path(_path).path == 'C:/test'
        _path = '~/test'
        assert_eq(Path(_path).path, HOME_PATH+'/test')
        assert Path(_path).path == HOME_PATH+'/test'
        assert Path('~').path == HOME_PATH
        os.chdir(Path('~').path)
        assert_eq(Path('./test').path, 'test')
        assert_eq(abs_path('./test'), HOME_PATH+'/test')
        assert_eq(Path(abs_path('./test')).path, HOME_PATH+'/test')
        _file = File('C:/test/hello.txt')
        assert _file.base == 'hello'
        assert _file.extn == 'txt'
        assert _file.dir == 'C:/test'

    def test_rel_path(self):

        _dir = Dir('C:/test')
        _adj = _dir.to_subdir('../out')
        assert _adj.path == 'C:/out'
        assert not _dir.contains(_adj)
        try:
            _dir.rel_path(_adj)
        except ValueError:
            pass
        else:
            raise AssertionError
        assert _dir.rel_path(_adj, allow_outside=True) == '../out'

    def test_write_yaml(self):

        # Test write yml
        _data = {'shot': 'Design/Production/Spots/{sequence}/Shots/{shot}'}
        _tmp_file = File(TMP_PATH+'/test.yml')
        print(_tmp_file)
        _tmp_file.write_yml(_data, force=True)
        pprint.pprint(_tmp_file.read_yml())
        assert _data == _tmp_file.read_yml()

        # Test write objects
        _work = testing.TEST_SHOT.to_work(task='test')
        _out = _work.to_output('publish', want_key={'output_type': False, 'ver': True})
        _notes = release.PRNotes('Release', 'module: notes')
        for _obj in [_out, _notes]:
            _file = Dir(TMP_PATH).to_file('test.yml')
            _file.write_yml(_obj, force=True)
            assert _file.read_yml()


class TestImage(unittest.TestCase):

    def test(self):

        _path = icons.find('Green Apple')
        assert Image(_path).to_res() == (144, 144)


class TestSeq(unittest.TestCase):

    def test(self):

        _path = abs_path('{}/test/image.0000.txt'.format(TMP_PATH))
        try:
            _seq = Seq(_path)
        except ValueError:
            pass
        else:
            raise AssertionError
        _path = abs_path('{}/test/image.%04d.txt'.format(TMP_PATH))
        _seq = Seq(_path)
        _dir = File(_path).to_dir()
        print(_path)
        print(_dir)
        _dir.delete(force=True)
        _dir.mkdir()
        for _idx in range(10):
            File(_path % _idx).touch()
        _dir.to_file('blah.txt').touch()
        assert_eq(_seq.to_frames(), list(range(10)))
        print(_seq[0])
        File(_seq[0]).delete(force=True)
        assert len(_seq.to_frames()) == 10
        assert len(_seq.frames) == 10
        assert len(_seq.to_frames(force=True)) == 9

        # Test delete
        assert _seq.exists()
        _seq.delete(force=True)
        assert not _seq.exists()

        # Test multiple tokens
        testing.TEST_DIR.flush(force=True)
        testing.TEST_DIR.to_file('pit010_comp_v005.1002.png.13492.tmp').touch()
        testing.TEST_DIR.find_seqs()

        # Test to_file
        assert clip.Seq('test.%04d.jpg').to_file().path == 'test.jpg'

        # Test contains
        _path = '/tmp/test.%04d.jpg'
        _seq = clip.Seq(_path)
        assert not _seq.contains('test.0001.jpg')
        assert _seq.contains('/tmp/test.0001.jpg')
        assert not _seq.contains('/tmp/test.1.jpg')

    def test_find_seqs(self):

        testing.TEST_DIR.flush(force=True)
        _seq_a = Seq(testing.TEST_DIR.to_file('blah/test.%03d.txt'))
        _seq_b = Seq(testing.TEST_DIR.to_file('test.%04d.tmp'))
        for _idx in range(1, 10):
            File(_seq_a[_idx]).touch()
            File(_seq_b[_idx]).touch()
        _seqs = testing.TEST_DIR.find_seqs(depth=2)
        assert _seqs
        assert len(_seqs) == 2
        assert _seq_a in _seqs
        assert _seq_b in _seqs
        assert _seq_a.to_frames() == list(range(1, 10))
        testing.enable_file_system(False)
        assert _seq_a.to_frames() == list(range(1, 10))
        testing.enable_file_system(True)

    def test_from_yml(self):

        _path = 'A:/test/image.%04d.jpg'
        _seq = Seq(_path)
        print(_seq.frames)
        testing.TEST_YML.write_yml([_seq], force=True)
        assert testing.TEST_YML.read_yml()

    def test_file_to_seq(self):

        _file = File('/asdasd/asdasd.dasd.2175.jpg')
        _seq = file_to_seq(_file)
        assert _seq == Seq('/asdasd/asdasd.dasd.%04d.jpg')

        _file = File('/asdasd/.2175.jpg')
        _seq = file_to_seq(_file)
        assert _seq == Seq('/asdasd/.%04d.jpg')

        _file = File('/asdasd/test.2175.jpg')
        _seq = file_to_seq(_file)
        assert _seq == Seq('/asdasd/test.%04d.jpg')

    def test_is_missing_frames(self):
        _seq = Seq('/tmp/test.%04d.jpg', frames=[1, 2, 3])
        assert not _seq.is_missing_frames()
        _seq = Seq('/tmp/test.%04d.jpg', frames=[1, 2, 4])
        assert _seq.is_missing_frames()


class TestPyFile(unittest.TestCase):

    def test_find_args(self):

        _LOGGER.info('FILE %s', __file__)
        _path = abs_path(__file__)
        _LOGGER.info('PATH %s', _path)
        _py_file = PyFile(_path)
        _LOGGER.info('PYFILE %s', _py_file)
        _LOGGER.info('PYFILE %s', _py_file)
        _def = _py_file.find_def('_test')

        assert _def
        assert _def.find_args()
        assert _def.find_arg('myarg').default is EMPTY
        assert _def.find_arg('myint').default == 1
        assert _def.find_arg('myfloat').default == 0.1
        assert _def.find_arg('mystr').default == 'a'
        assert _def.find_arg('mynone').default is None
        assert _def.find_arg('myexpr').default is None
        assert _def.find_arg('myglobal').default is None


def _test(
        myarg, myint=1, myfloat=0.1, mystr='a', mynone=None,
        myexpr=range(10), myglobal=_LOGGER):
    raise NotImplementedError
