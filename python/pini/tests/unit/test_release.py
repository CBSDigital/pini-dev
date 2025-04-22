import logging
import unittest

from pini import qt, testing
from pini.tools import release, error
from pini.utils import TMP, PyFile, to_snake

_LOGGER = logging.getLogger(__name__)


class TestRelease(unittest.TestCase):

    def test_autofix(self):

        for _name, _code, _fixed in [

                ('Check add trailing newline',
                 '\n'.join([
                     'import os',
                     '',
                     '',
                     'def test():',
                     '    pass']),
                 '\n'.join([
                     'import os',
                     '',
                     '',
                     'def test():',
                     '    pass',
                     ''])),

                ('Check remove trailing whitespace',
                 '\n'.join([
                     'import os',
                     '',
                     '',
                     'def test(): ',
                     '    pass',
                     '']),
                 '\n'.join([
                     'import os',
                     '',
                     '',
                     'def test():',
                     '    pass',
                     ''])),

                ('Check remove extra newlines',
                 '\n'.join([
                     'import os',
                     '',
                     '',
                     '',
                     'def test():',
                     '    pass',
                     '']),
                 '\n'.join([
                     'import os',
                     '',
                     '',
                     'def test():',
                     '    pass',
                     ''])),

                ('Check simple decorators',
                 '\n'.join([
                     'import os',
                     '',
                     '',
                     '',
                     '@decorator',
                     'def test():',
                     '    pass',
                     '']),
                 '\n'.join([
                     'import os',
                     '',
                     '',
                     '@decorator',
                     'def test():',
                     '    pass',
                     ''])),

                ('Check multiple decorators',
                 '\n'.join([
                     'import os',
                     '',
                     '',
                     '',
                     '@decorator',
                     '@decorator(',
                     '    ver=1)',
                     'def test():',
                     '    pass',
                     '']),
                 '\n'.join([
                     'import os',
                     '',
                     '',
                     '@decorator',
                     '@decorator(',
                     '    ver=1)',
                     'def test():',
                     '    pass',
                     ''])),

                ('Check decorator with trailing closing brackets',
                 '\n'.join([
                     'import os',
                     '',
                     '',
                     '',
                     '@decorator(',
                     '    ver=1, options={"result": [',
                     '        0, 1, 2',
                     ']})',
                     'def test():',
                     '    pass',
                     '']),
                 '\n'.join([
                     'import os',
                     '',
                     '',
                     '@decorator(',
                     '    ver=1, options={"result": [',
                     '        0, 1, 2',
                     ']})',
                     'def test():',
                     '    pass',
                     ''])),

                ('Check nested defs',
                 '\n'.join([
                     'import os',
                     'class Blah:',
                     '    def test(self):',
                     '        pass']),
                 '\n'.join([
                     'import os',
                     '',
                     '',
                     'class Blah:',
                     '',
                     '    def test(self):',
                     '        pass',
                     ''])),

                ('Check empty file',
                 '',
                 '',)

        ]:

            _LOGGER.info('RUNNING CHECK %s', _name)
            print('---- CODE ----')
            testing.clear_print(_code)
            print('---- FIXED ----')
            testing.clear_print(_fixed)

            _tmp = TMP.to_file('autofix_test.py')
            _tmp.write(_code, force=True)
            _file = release.CheckFile(_tmp)
            _file.apply_autofix(force=True)

            _result = _file.read()
            if _result != _fixed:
                print('---- RESULT ----')
                testing.clear_print(_result)
                raise RuntimeError('Result does not match')

            print()

    def _build_mod_docs_checks(self):
        return [

            # Check no module docs
            ('\n'.join([
                'def test():',
                '    pass']),
             'Missing module docs'),

            # Check module docs title trailing period
            ('\n'.join([
                '"""Blah"""',
                '',
                'def test():',
                '    pass']),
             'No trailing period in module docs title'),

            # Check module docs title capitalised
            ('\n'.join([
                '"""blah."""',
                '',
                'def test():',
                '    pass']),
             'Module docs title not capitalized'),
        ]

    def _build_def_docs_checks(self):
        return [

            # Check no def docs
            ('\n'.join([
                '"""Blah."""',
                '',
                'def test():',
                '    pass']),
             'Missing def docs'),

            # Check def docs title trailing period
            ('\n'.join([
                '"""Blah."""',
                '',
                'def test():',
                '    """My docs"""']),
             'No trailing period in def docs title'),

            # Check def docs title capitalised
            ('\n'.join([
                '"""Blah."""',
                '',
                'def test():',
                '    """my docs."""']),
             'Def docs title not capitalized'),

            # Check for missing arg
            ('\n'.join([
                '"""Blah."""',
                '',
                'def test(arg):',
                '    """My docs."""']),
             'Arg "arg" docs are missing'),

            # Check for empty arg
            ('\n'.join([
                '"""Blah."""',
                '',
                'def test(arg):',
                '    """My docs.'
                '',
                '    Args:',
                '        arg (str): ',
                '    """']),
             'Arg "arg" docs are missing'),

            # Check for empty arg type
            ('\n'.join([
                '"""Blah."""',
                '',
                'def test(arg):',
                '    """My docs.'
                '',
                '    Args:',
                '        arg (): some docs',
                '    """']),
             'Arg "arg" docs is missing type'),

            # Check for wrong order args
            ('\n'.join([
                '"""Blah."""',
                '',
                'def test(arg_a, arg_b):',
                '    """My docs.'
                '',
                '    Args:',
                '        arg_b (str): some docs',
                '        arg_a (str): some docs',
                '    """']),
             'Arg "arg_a" docs are in the wrong position'),

            # Check for superfluous arg docs
            ('\n'.join([
                '"""Blah."""',
                '',
                'def test(arg_a, arg_b):',
                '    """My docs.'
                '',
                '    Args:',
                '        arg_a (str): some docs',
                '        arg_b (str): some docs',
                '        arg_c (str): some docs',
                '    """']),
             'Arg "arg_c" docs are superflouous'),

            # Check for leading missing arg docs
            ('\n'.join([
                '"""Blah."""',
                '',
                'def test(arg_a, arg_b, arg_c=True, arg_d=True):',
                '    """My docs.'
                '',
                '    Args:',
                '        arg_b (str): some docs',
                '        arg_c (str): some docs',
                '    """']),
             'Arg "arg_a" docs are missing'),

            # Check for empty returns type
            ('\n'.join([
                '"""Blah."""',
                '',
                'def test():',
                '    """My docs.',
                '',
                '    Returns:',
                '        (): blah',
                '    """']),
             'Missing returns type'),

            # Check for empty returns type
            ('\n'.join([
                '"""Blah."""',
                '',
                'def test():',
                '    """My docs.',
                '',
                '    Returns:',
                '        (str): ',
                '    """']),
             'Missing returns body'),

            # Check allow superfluous if kwargs
            ('\n'.join([
                '"""Blah."""',
                '',
                'def test(**kwargs):',
                '    """My docs.',
                '',
                '    Args:',
                '        arg_a (str): some docs',
                '    """']),
             None),

            # Check leading superfluous
            ('\n'.join([
                '"""Blah."""',
                '',
                'def test(arg_c=None):',
                '    """My docs.',
                '',
                '    Args:',
                '        arg_a (str): some docs',
                '        arg_b (str): some docs',
                '        arg_c (str): some docs',
                '    """']),
             'Arg "arg_a" docs are superflouous'),

            # Check leading superfluous
            ('\n'.join([
                '"""Blah."""',
                '',
                'def test(arg_c=None):',
                '    """My docs.',
                '',
                '    Args:',
                '        arg_a (str): some docs',
                '        arg_b (str): some docs',
                '        arg_c (str): some docs',
                '    """']),
             'Arg "arg_a" docs are superflouous'),

        ]

    def _build_method_docs_checks(self):
        return [

            # Check leading superfluous in method
            ('\n'.join([
                '"""Blah."""',
                '',
                '',
                'class Test:',
                '    """Test docs."""',
                '',
                '    def test(self, arg_c=None):',
                '        """My docs.',
                '',
                '        Args:',
                '            arg_a (str): some docs',
                '            arg_b (str): some docs',
                '            arg_c (str): some docs',
                '        """']),
             'Arg "arg_a" docs are superflouous'),

            # Check ignore self in method
            ('\n'.join([
                '"""Blah."""',
                '',
                '',
                'class Test:',
                '    """Test docs."""',
                '',
                '    def test(self):',
                '        """My docs."""']),
             None),

            # Check ignore cls in class method
            ('\n'.join([
                '"""Blah."""',
                '',
                '',
                'class Test:',
                '    """Test docs."""',
                '',
                '    @classmethod',
                '    def test(cls):',
                '        """My docs."""']),
             None),

            # Test super-private
            ('\n'.join([
                '"""Blah."""',
                '',
                '',
                'class Test:',
                '    """Test docs."""',
                '',
                '    def __bool__(self):',
                '        return "HELLO"']),
             None),

            # Test init
            ('\n'.join([
                '"""Blah."""',
                '',
                '',
                'class Test:',
                '    """Test docs."""',
                '',
                '    def __init__(self):',
                '        pass']),
             'Missing def docs'),

            # Test ignore ui callbacks
            ('\n'.join([
                '"""Blah."""',
                '',
                '',
                'class Test:',
                '    """Test docs."""',
                '',
                '    def _redraw__Mov(self):',
                '        pass',
                '',
                '    def _callback__Mov(self):',
                '        pass',
                '',
                '    def _context__Mov(self):',
                '        pass',
                '']),
             None),

        ]

    def _build_class_docs_checks(self):
        return [

            # Check no def docs
            ('\n'.join([
                '"""Blah."""',
                '',
                'class Test:',
                '    pass']),
             'Missing class docs'),

        ]

    def test_check_docs(self):

        # Run tests
        for _code, _error in qt.progress_bar(
                self._build_mod_docs_checks() +
                self._build_def_docs_checks() +
                self._build_method_docs_checks() +
                self._build_class_docs_checks()):

            _LOGGER.info('RUNNING CHECK')
            print('\n---- CODE ----')
            testing.clear_print(_code)

            _tmp = TMP.to_file('docs_test.py')
            _tmp.write(_code, force=True)
            _file = release.CheckFile(_tmp)
            try:
                _file.apply_docs_check()
            except error.FileError as _exc:
                if str(_exc) != _error:
                    _error_s = f"'{_error}'" if _error else None
                    _LOGGER.info("REQUIRED %s", _error_s)
                    _LOGGER.info("RAISED   '%s'", _exc)
                    raise AssertionError('Errors do not match') from _exc
            else:
                if _error:
                    raise RuntimeError('No error raised')

        _LOGGER.info('DOCS CHECKS PASSED')

    def test_docs_suggestions(self):

        for _name, _code, _docs in [

                ('Basic test',
                 '\n'.join([
                     'def test():',
                     '   pass']),
                 '    """Test"""\n'),

                ('Longer name test',
                 '\n'.join([
                     'def test_longer_name():',
                     '   pass']),
                 '    """Test longer name"""\n'),

                ('Arg test',
                 '\n'.join([
                     'def test_longer_name(arg):',
                     '   pass']),
                 '    ' + '\n    '.join([
                     '"""Test longer name',
                     '',
                     'Args:',
                     '    arg (): ',
                     '"""']) + '\n'),

                ('Kwarg test',
                 '\n'.join([
                     'def test_longer_name(kwarg="a"):',
                     '   pass']),
                 '    ' + '\n    '.join([
                     '"""Test longer name',
                     '',
                     'Args:',
                     '    kwarg (str): ',
                     '"""']) + '\n'),

                ('Basic returns test',
                 '\n'.join([
                     'def test():',
                     '   return 10']),
                 '    ' + '\n    '.join([
                     '"""Test',
                     '',
                     'Returns:',
                     '    (): ',
                     '"""']) + '\n'),

                ('Existing docs test',
                 '\n'.join([
                     'def test_existing():',
                     '   """Some existing docs."""']),
                 '    ' + '\n    '.join([
                     '"""Some existing docs."""']) + '\n'),

                ('Existing multi-line test',
                 '\n'.join([
                     'def test_existing():',
                     '   """Some existing docs.',
                     '',
                     '   Some extra text',
                     '   """']),
                 '    ' + '\n    '.join([
                     '"""Some existing docs.',
                     '',
                     'Some extra text',
                     '"""']) + '\n'),

                ('Existing args test',
                 '\n'.join([
                     'def test_existing(arg_a):',
                     '    """Some existing docs.',
                     '',
                     '    Some extra text',
                     '',
                     '    Args:',
                     '        arg_a (str): wowee',
                     '    """']),
                 '    ' + '\n    '.join([
                     '"""Some existing docs.',
                     '',
                     'Some extra text',
                     '',
                     'Args:',
                     '    arg_a (str): wowee',
                     '"""']) + '\n'),

                ('Existing multi-line args test',
                 '\n'.join([
                     'def test_existing(arg_a, arg_b=1):',
                     '    """Some existing docs.',
                     '',
                     '    Some extra text',
                     '',
                     '    Args:',
                     '        arg_a (str): wowee',
                     '            some long args!',
                     '    """']),
                 '    ' + '\n    '.join([
                     '"""Some existing docs.',
                     '',
                     'Some extra text',
                     '',
                     'Args:',
                     '    arg_a (str): wowee',
                     '        some long args!',
                     '    arg_b (int): ',
                     '"""']) + '\n'),

                ('Long args to multi-line test',
                 '\n'.join([
                     'def test_existing(arg_a, arg_b=1):',
                     '    """Some existing docs.',
                     '',
                     '    Some extra text',
                     '',
                     '    Args:',
                     '        arg_a (str): wowee this is some some long args that will spill over because there are so many words',
                     '    """']),
                 '    ' + '\n    '.join([
                     '"""Some existing docs.',
                     '',
                     'Some extra text',
                     '',
                     'Args:',
                     '    arg_a (str): wowee this is some some long args that will spill over',
                     '        because there are so many words',
                     '    arg_b (int): ',
                     '"""']) + '\n'),

                ('Kwarg types test',
                 '\n'.join([
                     'def kwargs_test(',
                     '       mynone=None, mystr="s", myint=1, myfloat=0.0,'
                     '       myfloat2=2.0):',
                     '    pass']),
                 '    ' + '\n    '.join([
                     '"""Kwargs test',
                     '',
                     'Args:',
                     '    mynone (): ',
                     '    mystr (str): ',
                     '    myint (int): ',
                     '    myfloat (float): ',
                     '    myfloat2 (float): ',
                     '"""',
                     ''])),

                ('Method docs ignore self',
                 '\n'.join([
                     'class Test:',
                     '    def kwargs_test(self, arg_a):',
                     '        pass']),
                 '        ' + '\n        '.join([
                     '"""Kwargs test',
                     '',
                     'Args:',
                     '    arg_a (): ',
                     '"""',
                     ''])),

                ('Init has contructor',
                 '\n'.join([
                     'class Test:',
                     '    def __init__(self):',
                     '        pass']),
                 '        ' + '\n        '.join([
                     '"""Constructor."""',
                     ''])),

                ('Class method ignore cls',
                 '\n'.join([
                     'class Test:',
                     '',
                     '    @classmethod',
                     '    def class_method_test(cls):',
                     '        pass']),
                 '        ' + '\n        '.join([
                     '"""Class method test"""',
                     ''])),

        ]:
            _docs = '\n'.join(
                _line if _line.strip() else ''
                for _line in _docs.split('\n'))

            _tmp = TMP.to_file('docs_test.py')
            _tmp.write(_code, force=True)

            _py = PyFile(_tmp)
            _def = _py.find_def(recursive=True)
            _suggestion = release.suggest_docs(_def)
            _LOGGER.info('RUNNING CHECK %s', _name)
            print('\n---- CODE ----')
            testing.clear_print(_code)
            print('\n---- SUGGESTION ----')
            testing.clear_print(_suggestion)
            print('\n---- CORRECT DOCS ----')

            testing.clear_print(_docs)
            # print('\n----')

            for _d_line, _s_line in zip(_docs.split('\n'), _suggestion.split('\n')):
                if _d_line != _s_line:
                    _LOGGER.info(' - DOCS       %s', _d_line)
                    _LOGGER.info(' - SUGGESTION %s', _s_line)
                    break
            assert _docs == _suggestion
            print()

        _LOGGER.info('CHECKS PASSED')

    def test_remove_unused_imports(self):

        _names = set()
        for _name, _code, _fixed in qt.progress_bar([

            ('Basic import test',
             '\n'.join([
                 'import os',
                 'import sys',
                 '',
                 'def test():',
                 '    pass']),
             '\n'.join([
                 '',
                 'def test():',
                 '    pass'])),

            ('Basic from test',
             '\n'.join([
                 'from pini import testing',
                 'from maya_pini import open_maya',
                 '',
                 'def test():',
                 '    pass']),
             '\n'.join([
                 '',
                 'def test():',
                 '    pass'])),

            ('Nested from test',
             '\n'.join([
                 'from pini import testing',
                 '',
                 'def test():',
                 '    from maya_pini import open_maya',
                 '    pass']),
             '\n'.join([
                 '',
                 'def test():',
                 '    pass'])),

            ('Relative from test',
             '\n'.join([
                 'from pini import testing',
                 'from .. import open_maya',
                 '',
                 'def test():',
                 '    pass']),
             '\n'.join([
                 '',
                 'def test():',
                 '    pass'])),

            ('Nested relative from test',
             '\n'.join([
                 'from pini import testing',
                 '',
                 'def test():',
                 '    from .. import open_maya',
                 '    pass']),
             '\n'.join([
                 '',
                 'def test():',
                 '    pass'])),

            ('Aliased',
             '\n'.join([
                 'import sys',
                 'from pini import testing',
                 'from maya_pini import open_maya as pom',
                 '',
                 'def test():',
                 '    print(sys)']),
             '\n'.join([
                 'import sys',
                 '',
                 'def test():',
                 '    print(sys)'])),

            ('Aliased in list',
             '\n'.join([
                 'import sys',
                 'import os',
                 'from maya_pini import tex, open_maya as pom, hik',
                 '',
                 'def test():',
                 '    print(sys, tex, hik)']),
             '\n'.join([
                 'import sys',
                 'from maya_pini import tex, hik',
                 '',
                 'def test():',
                 '    print(sys, tex, hik)'])),

            ('Remove from list test',
             '\n'.join([
                 'import os',
                 'import sys',
                 '',
                 'from pini.utils import abs_path, File, cache_result',
                 '',
                 'def test():',
                 '    print(sys, abs_path, cache_result)']),
             '\n'.join([
                 'import sys',
                 '',
                 'from pini.utils import abs_path, cache_result',
                 '',
                 'def test():',
                 '    print(sys, abs_path, cache_result)']),
             ),

            ('Remove last from list test',
             '\n'.join([
                 'import os',
                 'import sys',
                 '',
                 'from pini.utils import abs_path, File, cache_result',
                 '',
                 'def test():',
                 '    print(sys, abs_path, File)']),
             '\n'.join([
                 'import sys',
                 '',
                 'from pini.utils import abs_path, File',
                 '',
                 'def test():',
                 '    print(sys, abs_path, File)']),
             ),

            ('Remove first from list test',
             '\n'.join([
                 'import os',
                 'import sys',
                 '',
                 'from pini.utils import abs_path, File, cache_result',
                 '',
                 'def test():',
                 '    print(sys, cache_result, File)']),
             '\n'.join([
                 'import sys',
                 '',
                 'from pini.utils import File, cache_result',
                 '',
                 'def test():',
                 '    print(sys, cache_result, File)']),
             ),

            ('Remove from multi line',
             '\n'.join([
                 'import os',
                 'import sys',
                 '',
                 'from pini.utils import (',
                 '    abs_path, File, cache_result)',
                 '',
                 'def test():',
                 '    print(sys, cache_result, File)']),
             '\n'.join([
                 'import sys',
                 '',
                 'from pini.utils import File, cache_result',
                 '',
                 'def test():',
                 '    print(sys, cache_result, File)']),
             ),

            ('Apply wrapping',
             '\n'.join([
                 'import sys',
                 '',
                 'from pini.utils import (',
                 '    File, cache_result,',
                 '    abs_path, HOME, TMP, TMP_PATH,',
                 '    single,',
                 '    Dir, Path, Video,',
                 '    get_method_to_file_cacher)',
                 '',
                 'def test():',
                 '    print(HOME, TMP, TMP_PATH)',
                 '    print(get_method_to_file_cacher, Video, Dir)',
                 '    print(sys, cache_result, File)']),
             '\n'.join([
                 'import sys',
                 '',
                 'from pini.utils import (',
                 '    File, cache_result, HOME, TMP, TMP_PATH, Dir, Video,',
                 '    get_method_to_file_cacher)',
                 '',
                 'def test():',
                 '    print(HOME, TMP, TMP_PATH)',
                 '    print(get_method_to_file_cacher, Video, Dir)',
                 '    print(sys, cache_result, File)']),
             ),

        ]):

            _LOGGER.info('RUNNING CHECK %s', _name)
            # print('---- CODE ----')
            # testing.clear_print(_code)

            # Write to disk
            assert _name not in _names
            _names.add(_name)
            _tmp = TMP.to_file(f'.pini/tests/{to_snake(_name)}.py')
            if not _tmp.exists() or _tmp.read() != _code:
                _tmp.write(_code, force=True)

            _orig_code = _tmp.read()

            _file = release.CheckFile(_tmp)
            _fixed_code = _file._batch_apply_pylint_unused_imports(
                write=False, force=True)

            # _fixed_code = _tmp.read()

            assert _orig_code == _code
            if _fixed_code != _fixed:
                print('CODE:')
                testing.clear_print(_code)
                print()
                print('FIXED:')
                testing.clear_print(_fixed_code)
                print()
                print('REQUIRED:')
                testing.clear_print(_fixed)
                raise RuntimeError('Results do not match')

    def test_repo(self):
        # _dev = os.environ['DEV']
        # _path = f'{_dev}/pini-dev'
        # _repo = release.PRRepo(_path)
        _repo = release.PINI
        print(_repo)
        print(_repo.read_version())
        print(_repo.version)

    def test_version(self):

        _ver = release.PRVersion('1.2.3')
        assert _ver.to_next('major').string == '2.0.0'
        assert _ver.to_next('minor').string == '1.3.0'
        assert _ver.to_next('patch').string == '1.2.4'
        assert _ver == release.PRVersion('1.2.3')
