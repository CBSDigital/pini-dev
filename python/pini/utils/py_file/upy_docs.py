"""Tools for managing python docstrings.

Docs are assumed to be google style.
"""

import logging
import re

from .. u_misc import basic_repr, single

_LOGGER = logging.getLogger(__name__)


class PyDefDocs(object):
    """Represents docstrings of a python function."""

    def __init__(self, docstring, def_):
        """Constructor.

        Args:
            docstring (str): docstring
            def_ (PyDef): parent python function
        """
        self.docstring = docstring or ''
        self.def_ = def_

        _body = self.docstring

        self.raises = None
        if 'Raises:' in _body:
            _body, _raises = _body.rsplit('Raises:', 1)
            self.raises = _raises.strip()

        self.returns = None
        if 'Returns:' in _body:
            _body, _returns = _body.rsplit('Returns:', 1)
            self.returns = _returns.strip()

        self.args_str = None
        _splitter = "\nArgs:\n"
        if _splitter in _body:
            _body, _args_str = _body.rsplit(_splitter, 1)
            self.args_str = _args_str.rstrip()

        self.header = _body.strip()
        _LOGGER.debug(' - HEADER %s', self.header.split('\n'))

        self.title = self.header.split('\n')[0]

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
            if not _line.startswith(' '*8):
                if not _line.startswith(' '*4):
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

    def to_str(self, mode='Raw'):
        """Obtain this docstring as a string.

        Args:
            mode (str): mode to retrive docstring
                Raw - full raw docstring
                Header - just the description (no args/result)
                SingleLine - header as a single line

        Returns:
            (str): docstring component
        """
        if mode == 'Raw':
            _result = self.docstring
        elif mode == 'Header':
            _result = self.header
        elif mode == 'SingleLine':
            _result = ' '.join(self.header.split())
        else:
            raise ValueError(mode)
        return _result

    def __repr__(self):
        return basic_repr(self, self.def_.name)


class _PyArgDocs(object):
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
