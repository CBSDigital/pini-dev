"""Tools for managing the emoji index.html parser."""

import logging

from html.parser import HTMLParser

_LOGGER = logging.getLogger(__name__)


class EmojiIndexParser(HTMLParser):
    """Parser for emoji set's index.html file."""

    _count = 0
    names = {}
    urls = {}

    def handle_starttag(self, tag, attrs):
        """Handle html tag.

        Args:
            tag (str): name of tag
            attrs (list): tag attrs
        """
        if not tag == 'img':
            return
        _title = _url = None
        for _key, _val in attrs:
            if _key == 'title':
                _title = _val
            elif _key == 'data-src':
                _url = _val
        if not _title:
            return
        for _find, _replace in [
                ('\u201c', '"'),
                ('\u201d', '"'),
                ('\u2019', "'"),
                ('\xc5', ''),
                ('\xe9', 'e'),
                ('\xe3', 'a'),
                ('\xed', 'i'),
                ('\xf4', 'o'),
                ('\xe7', 'c'),
                ('\xf1', 'n'),
        ]:
            _title = _title.replace(_find, _replace)
        self.names[_title] = self._count
        self.urls[_title] = _url
        self._count += 1
