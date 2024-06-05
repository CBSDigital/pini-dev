"""Tools for managing the choice manager.

This allows option menu choices to be managed in greater detail.
"""


class PUChoiceMgr(object):
    """Object for managing option menu choices."""

    def __init__(self, get_choices, get_default=None):
        """Constructor.

        Args:
            get_choices (fn): function to read options
            get_default (fn): function to read default value
        """
        self.get_choices = get_choices
        self.get_default = get_default

    @property
    def choices(self):
        """Obtain list of choices.

        Returns:
            (str list): options
        """
        return self.get_choices()

    @property
    def default(self):
        """Obtain default selection.

        Returns:
            (str): default
        """
        return self.get_default()
