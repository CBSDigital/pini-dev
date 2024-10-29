"""Tools for managing fail ui elements."""

import logging

from pini import dcc
from pini.utils import single, basic_repr, wrap_fn

_LOGGER = logging.getLogger(__name__)


class SCFail(object):
    """Represent a check failure."""

    def __init__(self, msg, node=None, fix=None, button_width=None):
        """Constructor.

        Args:
            msg (str): fail message
            node (any): fail node (if any)
            fix (fn): fix function (if any)
            button_width (int): override default button with in sanity check
                ui for this fail (to accommodate for long option names)
        """
        self.msg = msg
        self.actions = []
        self.node = node
        self.button_width = button_width
        if node:
            self.add_action('Select node', wrap_fn(dcc.select_node, node))
        if fix:
            self.add_action('Fix', fix, is_fix=True)

    @property
    def fix(self):
        """Locate this fail's fix function.

        Returns:
            (fn|None): fix fuction (if any)
        """
        return single([_action for _label, _action, _ in self.actions
                       if _label == 'Fix'], catch=True)

    def add_action(self, label, func, is_fix=False, index=None):
        """Append an action to this fail's action list.

        Args:
            label (str): action label
            func (fn): action function
            is_fix (bool): whether this action is a fix (so that a
                ui update can be triggered if it is executed)
            index (int): where to position action in list (default
                is append to end of list)
        """
        if index is None:
            self.actions.append((label, func, is_fix))
        else:
            self.actions.insert(index, (label, func, is_fix))

    def __repr__(self):
        return basic_repr(self, self.msg)
