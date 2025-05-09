"""Tools for managing the base reference class."""


class PathRef:
    """Represents a reference to a path on disk."""

    cmp_key = None

    @property
    def path(self):
        """Obtain path to this reference."""
        raise NotImplementedError

    def update(self, path):
        """Update this reference to a new path.

        Args:
            path (str): path to apply
        """
        raise NotImplementedError

    def __lt__(self, other):
        return self.cmp_key < other.cmp_key
