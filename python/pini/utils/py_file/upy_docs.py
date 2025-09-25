"""Tools for managing python docstrings.

Docs are assumed to be google style.
"""

import logging
import re

from ..u_misc import basic_repr, single
from ..u_text import add_indent

_LOGGER = logging.getLogger(__name__)


class PyDefDocs:
    """Represents docstrings of a python function."""

    def __init__(self, body, def_=None, def_name=None):
        """Constructor.

        Args:
            body (str): docstring
            def_ (PyDef): parent python function
            def_name (str): name of parent def
                (for repr if def not avaiable)
        """
        _LOGGER.debug('INIT PyDefDocs')
        self.body = body or ''
        self.def_ = def_
        self.def_name = def_name or def_.name

        _text = self.body

        self.raises = None
        if 'Raises:' in _text:
            _text, _raises = _text.rsplit('Raises:', 1)
            self.raises = _raises.strip()
            _LOGGER.debug(' - ADDED RAISES %s', self.raises)

        self.returns = None
        if 'Returns:' in _text:
            _text, _returns = _text.rsplit('Returns:', 1)
            self.returns = _returns.strip()
            _LOGGER.debug(' - ADDED RETURNS %s', self.returns)

        self.args_str = None
        _splitter = "\nArgs:\n"
        if _splitter in _text:
            _text, _args_str = _text.rsplit(_splitter, 1)
            self.args_str = _args_str.rstrip()

        self.header = _text.strip()
        _LOGGER.debug(' - HEADER %s', self.header.split('\n'))

        self.title = self.header.split('\n')[0]

    def add_arg(self, arg):
        """Add an arg to these docs.

        This can be used to automate adding kwargs docs.

        Args:
            arg (PyArgDoc): arg docs to add
        """
        _LOGGER.debug('ADD ARG %s', arg)
        if not self.args_str:
            # import pprint
            # pprint.pprint(self.body)
            # asdasd
            self.args_str = ''
            raise NotImplementedError
        _arg_docs = arg.docstring.replace('\n', '\n    ')
        _new_arg_s = self.args_str + f'\n    {_arg_docs}'
        assert self.body.count(self.args_str) == 1

        self.body = self.body.replace(self.args_str, _new_arg_s)
        self.args_str = _new_arg_s

    def find_arg(self, name, catch=False):
        """Find an argument of this docstring.

        Args:
            name (str): match by name
            catch (bool): no error if arg doc missing

        Returns:
            (PyArgDoc): arg docs
        """
        _args = self.find_args(catch=catch)
        return single(
            [_arg for _arg in _args if _arg.name == name], catch=True)

    def find_args(self, catch=False):
        """Find argument definitions in this docstring.

        Args:
            catch (bool): no error if fail to find args

        Returns:
            (PyArgDoc list): arg list
        """
        _LOGGER.debug('FIND ARGS %s', self)
        try:
            _args = self._read_args()
        except ValueError as _exc:
            if catch:
                return []
            raise _exc
        return _args

    def _read_args(self):
        """Read args documentation from these docs.

        Returns:
            (PyArgDoc list): arg list
        """
        if not self.args_str:
            return []

        # Separate out texts
        _arg_strs = []
        for _line in self.args_str.split('\n'):
            _LOGGER.log(9, 'LINE %s', _line)
            if not _line.startswith(' ' * 8):
                if not _line.startswith(' ' * 4):
                    _LOGGER.info(' - FAILED TO READ ARGS %s', self)
                    raise ValueError
                _arg_strs.append(_line.strip())
            else:
                _arg_strs[-1] += '\n' + _line[4:]

        # Build arg objects
        _args = []
        for _arg_str in _arg_strs:
            _LOGGER.debug('ARG %s', _arg_str.split('\n'))
            _arg = _PyArgDocs(_arg_str)
            _args.append(_arg)

        return _args

    def set_title(self, title):
        """Update title of these docs.

        Args:
            title (str): new title to apply
        """
        assert self.body.count(self.title) == 1
        self.body = self.body.replace(self.title, title)
        self.title = title

    def to_str(self, mode='Raw', def_=None):
        """Obtain this docstring as a string.

        Args:
            mode (str): mode to retrive docstring
                Raw - full raw docstring
                Header - just the description (no args/result)
                SingleLine - header as a single line
                Code - as this docstring appears in the code (ie. with indent)
                Clean - with indentation removed (but with triple quotes)
            def_ (PyDef): override def to read indent from (useful for
                transferring docs between different functions)

        Returns:
            (str): docstring component
        """
        _def = def_ or self.def_
        if mode == 'Raw':
            _result = self.body
        elif mode == 'Header':
            _result = self.header
        elif mode == 'SingleLine':
            _result = ' '.join(self.header.split())
        elif mode == 'Code':
            assert _def
            _indent = _def.indent + '    '
            _result = add_indent(self.to_str('Clean'), indent=_indent)
            _result = '\n'.join(_line.rstrip() for _line in _result.split('\n'))
        elif mode == 'Clean':
            # assert self.def_
            _tail = '"""' if '\n' not in self.body else '\n"""'
            _result = f'"""{self.body}{_tail}'
        else:
            raise ValueError(mode)
        return _result

    def __repr__(self):
        return basic_repr(self, self.def_name)


class _PyArgDocs:
    """Represents an argument definition in a docstring."""

    def __init__(self, docstring):
        """Constructor.

        Args:
            docstring (str): docstring body
        """
        self.docstring = docstring
        self.name, self.type_, _, self.body = re.split('[():]', docstring, 3)
        self.name = self.name.strip()
        self.body = self.body.strip()

    def to_str(self, mode='Body'):
        """Obtain these docs as a string.

        Args:
            mode (str): data to retrieve
                Raw - full docs
                Body - docs text without name/type
                SingleLine - body without newlines

        Returns:
            (str): docs data
        """
        if mode == 'Raw':
            _result = self.docstring
        elif mode == 'Body':
            _result = self.body
        elif mode == 'SingleLine':
            _result = self.body.replace('\n    ', ' ')
        elif mode == 'HTML':
            _result = f'<b>{self.name}</b> ({self.type_}) - {self.body}'
        else:
            raise ValueError(mode)
        return _result

    def __repr__(self):
        return basic_repr(self, self.name)
