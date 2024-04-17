"""Tools for managing python args."""

from ..u_misc import EMPTY, basic_repr


class PyArg(object):
    """Represents an argument to a python function."""

    def __init__(self, name, default=EMPTY):
        """Constructor.

        Args:
            name (str): arg name
            default (any): arg default
        """
        self.name = name
        self.default = default
        self.type_ = type(default) if default is not EMPTY else None

    def __repr__(self):
        return basic_repr(self, self.name)
