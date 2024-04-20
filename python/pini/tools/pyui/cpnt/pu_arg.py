"""Use to manage function arguments in pyui."""

# pylint: disable=too-many-instance-attributes

from pini.utils import basic_repr


class PUArg(object):
    """Represents a function argument.

    Settings are passed to each arg via the pyui.install decorator applied
    to the parent function.
    """

    def __init__(
            self, name, py_arg, py_def, pyui_file, clear=False,
            browser=False, choices=None, label_w=None):
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
            label_w (int): override label width (in pixels)
        """
        self.name = name
        self.default = py_arg.default

        self.py_arg = py_arg
        self.py_def = py_def
        self.pyui_file = pyui_file

        self.clear = clear
        self.browser = browser
        self.choices = choices
        self.label_w = label_w

    def __repr__(self):
        return basic_repr(self, self.name)
