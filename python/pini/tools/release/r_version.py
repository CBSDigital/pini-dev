"""Tools for managing release versions."""

from pini.utils import basic_repr

RELEASE_TYPES = ('major', 'minor', 'patch')


class PRVersion:
    """Represents a release version.

    This is defined by a 3 number string with value representing
    major/minor/patch indices (eg. 1.2.3).
    """

    def __init__(self, string, mtime=None):
        """Constructor.

        Args:
            string (str): version string (eg. 1.2.3)
            mtime (float): release time
        """
        self.string = string
        _tokens = [int(_token) for _token in string.split('.')]
        self.major, self.minor, self.patch = _tokens
        self.cmp_str = '.'.join(f'{_val:03d}' for _val in _tokens)
        self.mtime = mtime

    def to_str(self) -> str:
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

    def __eq__(self, other):
        return self.cmp_str == other.cmp_str

    def __lt__(self, other):
        return self.cmp_str < other.cmp_str

    def __le__(self, other):
        return self.cmp_str <= other.cmp_str

    def __repr__(self):
        _ver_s = f'{self.major:d}.{self.minor:d}.{self.patch:d}'
        return basic_repr(self, _ver_s)


DEV_VER = PRVersion('999.0.0')
ZERO_VER = PRVersion('0.0.0')
