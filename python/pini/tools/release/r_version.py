"""Tools for managing release versions."""

from pini.utils import six_cmp

RELEASE_TYPES = ('major', 'minor', 'patch')


class PRVersion(object):
    """Represents a release version.

    This is defined by a 3 number string with value representing
    major/minor/patch indices (eg. 1.2.3).
    """

    def __init__(self, string):
        """Constructor.

        Args:
            string (str): version string (eg. 1.2.3)
        """
        self.string = string
        _tokens = [int(_token) for _token in string.split('.')]
        self.major, self.minor, self.patch = _tokens
        self.cmp_str = '.'.join('{:03d}'.format(_val) for _val in _tokens)

    def to_str(self):
        """Get version as string.

        Returns:
            (str): version string
        """
        return self.string

    def to_next(self, type_):
        """Get next increment from this version.

        Args:
            type_ (str): increment type

        Returns:
            (PRVersion): next version
        """
        if type_ == 'major':
            _vals = self.major + 1, 0, 0
        elif type_ == 'minor':
            _vals = self.major, self.minor + 1, 0
        elif type_ == 'patch':
            _vals = self.major, self.minor, self.patch + 1
        else:
            raise ValueError(type_)
        return PRVersion('.'.join(str(_val) for _val in _vals))

    def __cmp__(self, other):
        return six_cmp(self.cmp_str, other.cmp_str)

    def __eq__(self, other):
        return self.cmp_str == other.cmp_str

    def __lt__(self, other):
        return self.cmp_str < other.cmp_str

    def __le__(self, other):
        return self.cmp_str <= other.cmp_str

    def __repr__(self):
        return '<{}:{:d}.{:d}.{:d}>'.format(
            type(self).__name__, self.major, self.minor, self.patch)


DEV_VER = PRVersion('999.0.0')
ZERO_VER = PRVersion('0.0.0')
