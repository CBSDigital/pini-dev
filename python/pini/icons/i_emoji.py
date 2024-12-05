"""Tools for managing the emoji object."""

import logging
import re

from pini.utils import File

_LOGGER = logging.getLogger(__name__)


class Emoji(File):
    """Represents an emoji image file as part of a set."""

    def __init__(self, file_, name, url):
        """Constructor.

        Args:
            file_ (str): path to image file
            name (str): file label
            url (str): emojipedia download url
        """
        super().__init__(file_)
        self.name = name
        self.url = url
        self.index = int(self.path.split('.')[-2])

    def to_unicode(self):
        """Get unicode characters for this emoji.

        Returns:
            (unicode): unicode char
        """
        _hash = (re.split('[_.]', self.url.upper())[-2]).split('-')[0]
        return eval(fr"u'\U000{_hash}'")  # pylint: disable=eval-used

    def __repr__(self):
        _type = type(self).__name__.strip('_')
        return f'<{_type}[{self.index:d}]:{self.name}>'
