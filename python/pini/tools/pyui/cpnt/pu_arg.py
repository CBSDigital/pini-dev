"""Use to manage function arguments in pyui."""

# pylint: disable=too-many-instance-attributes

import collections
import types

from pini.utils import basic_repr, to_nice

from ..cpnt import pu_choice_mgr


class PUArg(object):
    """Represents a function argument.

    Settings are passed to each arg via the pyui.install decorator applied
    to the parent function.
    """

    def __init__(
            self, name, py_arg, py_def, pyui_file, clear=False,
            browser=False, choices=None, selection=False, label=None,
            label_w=None, docs=None, callback=None):
        """Constructor.

        Args:
            name (str): arg name
            py_arg (PyArg): corresponding PyFile arg
            py_def (PyDef): corresponding PyFile def
            pyui_file (PUFile): parent pyui file
            clear (bool): build a clear button to this arg
                (for resetting a text field)
            browser (bool|str): apply browser button
                bool - apply ExistingFile mode
                str - apply this file mode to the browser
            choices (str list): apply options list
            selection (bool|str): apply get selected node button
                bool - any selected node
                str - apply node type filter
            label (str): override arg label
            label_w (int): override label width (in pixels)
            docs (str): arg documentation
            callback (func): callback to be executed if this field is edited
        """
        self.name = name
        self.default = py_arg.default
        self.label = label or to_nice(self.name).capitalize()

        self.py_arg = py_arg
        self.py_def = py_def
        self.pyui_file = pyui_file

        self.clear = clear
        self.choices = choices
        self.selection = selection
        self.callback = callback

        self.browser = browser
        self.browser_mode = None if browser is True else browser

        self.docs = docs
        self.label_w = label_w

    @property
    def uid(self):
        """Obtain uid for this arg.

        Returns:
            (str): uid
        """
        return '.'.join([self.pyui_file.uid, self.py_def.name, self.name])

    def to_choices(self):
        """Obtain list of choices for this arg.

        Returns:
            (str list): choices
        """
        if not self.choices:
            return None
        if isinstance(
                self.choices, (tuple, list, set, collections.abc.Iterable)):
            return self.choices
        if isinstance(self.choices, pu_choice_mgr.PUChoiceMgr):
            return self.choices.choices
        if isinstance(self.choices, types.FunctionType):
            return self.choices()
        raise ValueError(self.choices)

    def to_default(self):
        """Obtain default choice for this arg.

        Returns:
            (str): default selection
        """
        if not self.choices:
            return None
        if isinstance(
                self.choices, (tuple, list, set, collections.abc.Iterable)):
            return self.default
        if isinstance(self.choices, pu_choice_mgr.PUChoiceMgr):
            return self.choices.default
        if isinstance(self.choices, types.FunctionType):
            return self.default
        raise ValueError(self.choices)

    def __repr__(self):
        return basic_repr(self, self.name)
