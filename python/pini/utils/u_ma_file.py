"""Tools for managing and updating ma files.

This is achieved via text parsing (ie. outside maya).
"""

import logging

from .u_misc import basic_repr, single
from .u_filter import passes_filter
from .path import MetadataFile, File

_LOGGER = logging.getLogger(__name__)
_COL = 'PowderBlue'


class _MaExpr:  # pylint: disable=too-many-instance-attributes
    """Represents an expression in an ma file."""

    def __init__(self, body, line_n, tokens=None, cmd=None):
        """Constructor.

        Args:
            body (str): expression body
            line_n (int): line number of expression
            tokens (str list): override tokens (words in line)
            cmd (str): override command (first token in line)
        """
        self.body = body
        self.new_body = body
        self.updated = False

        self.line_n = line_n
        self.tokens = tokens or body.split()
        self.cmd = cmd or self.tokens[0]

        self.indented = body[0].isspace()
        self.comment = body.startswith('\\')
        self.children = []

    def replace(self, find, replace):
        """Replace text in this expression.

        Updates are only applied when the ma file is saved.

        Args:
            find (str): text to find
            replace (str): text to replace
        """
        self.updated = True
        self.new_body = self.new_body.replace(find, replace)

    def read_flag(self, flag):
        """Read the given flag on this expression.

        eg. file -ns blah -> ns = blah

        Args:
            flag (str): flag to read

        Returns:
            (str): flag value
        """
        return self.tokens[self.tokens.index('-'+flag)+1].strip('"')

    def __repr__(self):
        return basic_repr(self, self.cmd)


class _MaCreateNode(_MaExpr):
    """Represents a createNode expression in an ma file."""

    _name = None

    @property
    def name(self):
        """Obtain node name (ie. read -n flag) for this expression.

        Returns:
            (str): node name
        """
        if not self._name:
            self._name = self.read_flag('n')
        return self._name

    @property
    def type_(self):
        """Obtain node type.

        Returns:
            (str): type
        """
        return self.tokens[1]

    def __repr__(self):
        _type = type(self).__name__.strip('_')
        return f'<{_type}[{self.type_}]:{self.name}>'


class MaFile(MetadataFile):
    """Represents a maya ascii file."""

    _exprs = None

    def __init__(self, file_):
        """Constructor.

        Args:
            file_ (str): path to ma file
        """
        super().__init__(file_)
        self.body = self.read()
        if self.extn != 'ma':
            raise ValueError(file_)

    def find_exprs(self, cmd=None, progress=False):
        """Find expressions in this ma file.

        Args:
            cmd (str): filter by command (eg. file, fileInfo, createNode)
            progress (bool): show progress on read expressions

        Returns:
            (MaExpr list): matching expressions
        """
        _exprs = []
        for _expr in self._read_exprs(progress=progress):
            if cmd and _expr.cmd != cmd:
                continue
            _exprs.append(_expr)
        return _exprs

    def find_node(self, catch=True, **kwargs):
        """Find a matching createNode expression in this ma file.

        Args:
            catch (bool): supress error if no single expression found

        Returns:
            (MaCreateNode|None): matching expressin (if any)
        """
        _nodes = self.find_nodes(**kwargs)
        return single(_nodes, catch=catch)

    def find_nodes(self, type_=None, filter_=None, name=None, progress=False):
        """Find createNode expressions in this ma file.

        Args:
            type_ (str): filter by node type
            filter_ (str): apply filter to name
            name (str): filter by exact name
            progress (bool): show progress on read expressions

        Returns:
            (MaCreateNode list): matching createNode expressions
        """
        _nodes = []
        for _node in self.find_exprs(cmd='createNode', progress=progress):

            if type_ and _node.type_ != type_:
                continue

            # Name filters last - expensive
            if filter_ and not passes_filter(_node.name, filter_):
                continue
            if name and _node.name != name:
                continue

            _nodes.append(_node)
        return _nodes

    def _read_exprs(self, progress=False, force=False):
        """Read expressions in this ma file.

        Args:
            progress (bool): show progress on read expressions
            force (bool): force re-read expressions from disk

        Returns:
            (MaExpr list): all expressions
        """
        from pini import qt
        if force or self._exprs is None:

            # Read lines from file
            _lines = self.body.split(';\n')
            if progress:
                _lines = qt.progress_bar(
                    _lines, f'Reading MaFile {self.nice_size()}',
                    col=_COL)

            # Convert to expressions
            self._exprs = []
            _line_n = 1
            _parent = None
            for _text in _lines:

                _n_lines = _text.count('\n') + 1

                _class = _MaExpr
                _tokens = _text.split()
                if _text.startswith('//'):
                    _cmd = None
                else:
                    _cmd = _tokens[0]
                    if _cmd == 'createNode':
                        _class = _MaCreateNode
                _expr = _class(
                    _text, line_n=_line_n, tokens=_tokens, cmd=_cmd)
                self._exprs.append(_expr)

                # Keep track of parenting
                if not _expr.indented:
                    _parent = _expr
                else:
                    _parent.children.append(_expr)

                _line_n += _n_lines

        return self._exprs

    def read_contents(self, progress=True, force=False):
        """Read contents of this ma file.

        Args:
            progress (bool): show progress on read expressions
            force (bool): force re-read expressions from disk
        """
        self._read_exprs(progress=progress, force=force)

    def remove(self, expr):
        """Remove the given expression from this file.

        Args:
            expr (MaExpr): expression to remove
        """
        _LOGGER.debug('REMOVING %s', expr)
        for _expr in [expr] + expr.children:
            _LOGGER.debug(' - REMOVE %s', _expr)
            self._exprs.remove(_expr)

    def save(self, file_=None, force=False):
        """Save this ma file with any expression updates applied.

        Args:
            file_ (str): path to save to
            force (bool): overwrite existing without confirmation
        """
        _file = File(file_ or self)

        _new_body = ''
        for _expr in self._exprs:
            _new_body += _expr.body
            if not _expr.comment:
                _new_body += ';'
            _new_body += '\n'

        # _new_body = ''
        # _updated = False
        # for _expr in self._exprs:
        #     if not _expr.updated:
        #         continue
        #     assert _new_body.count(_expr.body) == 1
        #     _new_body = _new_body.replace(_expr.body, _expr.new_body)
        #     _updated = True

        # if not _updated:
        #     _title = 'Confirm {}'.format('Save' if file_ else 'Update')
        #     qt.ok_cancel('Nothing was updated', title=_title)

        _file.write(_new_body, force=force)

        return _file
