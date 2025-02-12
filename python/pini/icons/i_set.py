"""Tools for managing emoji sets (eg. android, emojidex)."""

import codecs
import logging

from pini.utils import (
    Seq, cache_property, single, to_snake, passes_filter, cache_result)

from . import i_parser, i_emoji

_LOGGER = logging.getLogger(__name__)


class EmojiSet(Seq):
    """Represents a set of emojis with an index.html descriptor."""

    def __init__(self, *args, **kwargs):
        """Constructor."""
        super().__init__(*args, **kwargs)
        self.index = f'{self.dir}/index.html'
        self._matches = {}

    def find(self, match, catch=False, verbose=0):
        """Find the path to an emoji in this set.

        Args:
            match (str|int): match by name or index
            catch (bool): no error if exactly one emoji is not found
            verbose (int): print process data

        Returns:
            (str): path to emoji
        """
        _emoji = self.find_emoji(match=match, catch=catch, verbose=verbose)
        if not _emoji:
            return None
        return _emoji.path

    def find_emoji(self, match, catch=False, verbose=0):
        """Find an emoji in this set.

        Args:
            match (str|int): match by name or index
            catch (bool): no error if exactly one emoji is not found
            verbose (int): print process data

        Returns:
            (Emoji): matching emoji
        """
        _emoji = self._matches.get(match)
        if not _emoji:
            _emojis = []

            # Find index to match
            _idx = None
            if isinstance(match, int):
                _idx = match
            elif isinstance(match, str) and match.isdigit():
                _idx = int(match)

            # Match by index/name/filter
            for _o_emoji in self._emojis:  # pylint: disable=not-an-iterable
                if isinstance(match, str):
                    if _o_emoji.name.lower() == match.lower():
                        _emoji = _o_emoji
                        break
                    if passes_filter(_o_emoji.name.lower(), match.lower()):
                        _emojis.append(_o_emoji)
                if _idx is not None and _o_emoji.index == _idx:
                    _emoji = _o_emoji
                    break

            # Handle fail
            if not _emoji:
                try:
                    _emoji = single(_emojis, catch=catch)
                except ValueError as _exc:
                    if verbose:
                        for _emoji in sorted(_emojis):
                            _LOGGER.info(' - %s', _emoji.name)
                    _emojis = sorted([_emoji.name for _emoji in _emojis])
                    raise ValueError(
                        f'Failed to match {match} - {_emojis}') from _exc

            self._matches[match] = _emoji

        return _emoji

    @cache_result
    def find_grp(self, name):
        """Find named group of emojis within this set.

        Args:
            name (str): name of group (eg. fruit)

        Returns:
            (str list): list of emoji paths
        """
        from . import i_const
        _name = name
        if not _name.isupper():
            _name = to_snake(name)
        _name = '_' + _name.upper()
        _names = getattr(i_const, _name)
        return tuple(self.find(_name) for _name in _names)

    @cache_property
    def _emojis(self):
        """Retrieve full emoji list.

        Returns:
            (Emoji list): all emojis
        """
        # pylint: disable=no-member

        _emojis = []
        for _name, _idx in self._html_parser.names.items():
            _url = self._html_parser.urls[_name]
            _emoji = i_emoji.Emoji(file_=self[_idx], name=_name, url=_url)
            _emojis.append(_emoji)

        return tuple(_emojis)

    @cache_property
    def _html_parser(self):
        """Retrieve emoji index parser object.

        Returns:
            (EmojiIndexParser): parser
        """
        _hook = codecs.open(self.index, encoding='utf-8')
        _body = _hook.read()
        _hook.close()
        _parser = i_parser.EmojiIndexParser()
        _parser.feed(_body)
        return _parser
