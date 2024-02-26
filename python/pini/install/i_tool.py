"""Tools for managing artists tools to be installed into dccs.

eg. PiniHelper is a tool which has options right-click options.
"""

import copy

from pini.utils import basic_repr, is_pascal


class PITool(object):
    """Container class for a pini tool."""

    def __init__(self, name, command, icon, label=None):
        """Constructor.

        Args:
            name (str): tool name/uid
            command (str): tool command
            icon (str): path to tool icon
            label (str): tool label
        """
        self.name = name
        if not is_pascal(self.name):
            raise ValueError(self.name)
        self.command = command
        self.icon = icon
        self.label = label or self.name

        self.context_items = []

    def add_context(self, item):
        """Add a context (right-click) option to this tool.

        Args:
            item (PITool): context option
        """
        self.context_items.append(item)

    def add_divider(self, name=None):
        """Add context menu divider.

        Args:
            name (str): ui element uid
        """
        self.add_context(PIDivider(name))

    def duplicate(self, command=None):
        """Duplicate this tool.

        Args:
            command (str): override command

        Returns:
            (PITool): tool
        """
        _dup = copy.copy(self)
        if command:
            _dup.command = command
        return _dup

    def to_uid(self, prefix):
        """Obtain uid for this tool, used to replace any existing instances.

        Args:
            prefix (str): shelf/menu prefix

        Returns:
            (str): tool uid (eg. PI_PiniHelper)
        """
        return prefix+'_'+self.name

    def __repr__(self):
        return basic_repr(self, self.name)


class PIDivider(object):
    """Used to represent a divider/separator."""

    def __init__(self, name):
        """Constructor.

        Args:
            name (str): divider name/uid
        """
        self.name = name
        if not is_pascal(self.name):
            raise ValueError(self.name)

    def __repr__(self):
        return basic_repr(self, self.name)
