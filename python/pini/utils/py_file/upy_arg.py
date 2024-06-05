"""Tools for managing python args."""

from ..u_misc import EMPTY, basic_repr


class PyArg(object):
    """Represents an argument to a python function."""

    def __init__(self, name, parent, default=EMPTY):
        """Constructor.

        Args:
            name (str): arg name
            parent (PyDef): parent python def
            default (any): arg default
        """
        self.name = name
        self.default = default
        self.type_ = type(default) if default is not EMPTY else None
        self.parent = parent

    def to_docs(self, mode='Object'):
        """Obtain docstrings for this argument.

        Args:
            mode (str): type of data to retrieve
                Object - arg docs object containing all data
                SingleLine - docs as a single line string

        Returns:
            (PyArgDocs|str): docs
        """
        _docs = self.parent.to_docs().find_arg(self.name, catch=True)
        if not _docs:
            return None
        _result = None
        if mode == 'Object':
            _result = _docs
        elif mode == 'SingleLine':
            if _docs:
                _result = _docs.to_str('SingleLine')
        else:
            raise ValueError(mode)
        return _result

    def __repr__(self):
        return basic_repr(self, self.name)
