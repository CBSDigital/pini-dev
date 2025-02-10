"""Tools for managing mel files."""

from .cache import cache_property
from .path import File
from .u_misc import single, last, basic_repr


class _MelExpr:
    """Represents an expressing in a mel file."""

    def __init__(self, text):
        """Constructor.

        Args:
            text (str): expression text
        """
        self.text = text.strip()
        self._tokens = text.split()
        self.func = self._tokens[0]

    def read_flag(self, flag, default=-1):
        """Read the value of the given flag in this expression.

        Args:
            flag (str): flag to read
            default (any): value to return if item not found

        Returns:
            (str): flag value
        """
        _flag = f' -{flag} '
        if _flag not in self.text:
            if default != -1:
                return default
            raise ValueError(flag)

        _idx = self.text.find(_flag) + len(_flag)
        _val = ''
        _in_quotes = False
        for _idx in range(_idx, len(self.text)):
            _escaped = _idx and self.text[_idx - 1] == '\\'
            _chr = self.text[_idx]
            if not _escaped and _chr == '"':
                _in_quotes = not _in_quotes
            if not _in_quotes and not _escaped and _chr == '-':
                break
            _val += _chr
        _val = _val.strip().strip('"')
        _val = _val.replace('\\\\', '\\')
        _val = _val.replace('\\n', '\n')
        _val = _val.replace('\\t', '\t')
        _val = _val.replace('\\"', '"')
        return _val

    def __repr__(self):
        return basic_repr(self, self.func)


class MelFile(File):
    """Represents a file containing mel code."""

    def find_expr(self, **kwargs):
        """Find an expression in this file.

        Returns:
            (MelExpr): matching expression
        """
        return single(self.find_exprs(**kwargs))

    def find_exprs(self, func=None, annotation=None):
        """Find expressions in this file.

        Args:
            func (str): filter by function name
            annotation (str): filter by annotation

        Returns:
            (MelExpr): list of matching expressions
        """
        _exprs = list(self.exprs)
        if func:
            _exprs = [_expr for _expr in _exprs if _expr.func == func]
        if annotation:
            _exprs = [_expr for _expr in _exprs
                      if _expr.read_flag('annotation', None) == annotation]
        return _exprs

    @cache_property
    def exprs(self):
        """Read list of expressions from this file.

        Returns:
            (MelExpr tuple): expressions
        """
        _text = self.read()
        assert isinstance(_text, str)
        _exprs = []
        _expr_text = ''
        _in_quotes = False
        for _last, (_idx, _chr) in last(enumerate(_text)):
            assert isinstance(_chr, str)
            _escaped = _idx and _text[_idx - 1] == '\\'
            if not _escaped and _chr == '"':
                _in_quotes = not _in_quotes
            _expr_text += _chr
            if not _in_quotes and (
                    _last or
                    (not _escaped and _chr == ';')):
                _expr = _MelExpr(_expr_text)
                _exprs.append(_expr)
                _expr_text = ''

        return tuple(_exprs)
