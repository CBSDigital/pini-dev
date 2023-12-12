"""Tools for managing artists tools to be installed into dccs.

eg. PiniHelper is a tool which has options right-click options.
"""

from pini.utils import basic_repr


class CITool(object):
    """Container class for a pini tool."""

    def __init__(self, name, command, icon, label):
        """Constructor.

        Args:
            name (str): tool name/uid
            command (str): tool command
            icon (str): path to tool icon
            label (str): tool label
        """
        self.name = name
        self.command = command
        self.icon = icon
        self.label = label

        self.context_items = []

    def add_context(self, item):
        """Add a context (right-click) option to this tool.

        Args:
            item (CITool): context option
        """
        self.context_items.append(item)

    def add_divider(self, name=None):
        """Add context menu divider.

        Args:
            name (str): ui element uid
        """
        self.add_context(CIDivider(name))

    def __repr__(self):
        return basic_repr(self, self.name)


class CIDivider(object):
    """Used to represent a divider/separator."""

    def __init__(self, name):
        """Constructor.

        Args:
            name (str): divider name/uid
        """
        self.name = name

    def __repr__(self):
        return basic_repr(self, self.name)
