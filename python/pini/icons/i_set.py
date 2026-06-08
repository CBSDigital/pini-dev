"""Tools for managing emoji sets (eg. android, emojidex)."""

import codecs
import logging

from pini.utils import (
    Seq, cache_property, to_snake, passes_filter, cache_result,
    File, Dir, cache_method_to_file)

from . import i_parser, i_emoji

_LOGGER = logging.getLogger(__name__)
_DIR = File(__file__).to_dir()


class EmojiSet(Seq):
    """Represents a set of emojis with an index.html descriptor."""

    def __init__(self, *args, **kwargs):
        """Constructor."""
        super().__init__(*args, **kwargs)
        self.index = f'{self.dir}/index.html'
        _name = Dir(self.dir).filename
        self.cache_fmt = _DIR.to_file(f'cache/.{_name}_{{func}}.pkl').path
        self._matches = {}

    def find(self, match, catch=False):
        """Find the path to an emoji in this set.

        Args:
            match (str|int): match by name or index
            catch (bool): no error if exactly one emoji is not found

        Returns:
            (str): path to emoji
        """
        _emoji = self.find_emoji(match=match, catch=catch)
        if not _emoji:
            return None
        return _emoji.path

    def find_emoji(self, match, catch=False):
        """Find an emoji in this set.

        Args:
            match (str|int): match by name or index
            catch (bool): no error if exactly one emoji is not found

        Returns:
            (Emoji): matching emoji
        """
        _LOGGER.debug('FIND EMOJI %s', match)
        _emoji = self._matches.get(match)
        if _emoji:
            return _emoji

        # Find index/str to match
        _match_i = None
        if isinstance(match, int):
            _match_i = match
        elif isinstance(match, str) and match.isdigit():
            _match_i = int(match)
        _match_s = None
        if isinstance(match, str):
            _match_s = match.lower()
        _LOGGER.debug(' - MATCH "%s" "%s"', _match_i, _match_s)
        if _match_i is None and not _match_s:
            raise TypeError(match, type(match))

        # Match by index/name/filter
        for _o_emoji in self._emojis:  # pylint: disable=not-an-iterable
            if _match_s and _o_emoji.name.lower() == _match_s:
                _emoji = _o_emoji
                break
            if _match_i is not None and _o_emoji.index == _match_i:
                _emoji = _o_emoji
                break

        if _emoji:
            self._matches[match] = _emoji
            return _emoji

        # Handle fail
        if catch:
            return None
        _emojis = '/'.join(sorted([
            _o_emoji.name for _o_emoji in self._emojis
            if passes_filter(_o_emoji.name.lower(), _match_s)]))
        raise ValueError(
            f'Failed to match {match} - possibly {_emojis}?')

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
        _emojis = []
        for _idx, _name, _url in self._to_parser_data():
            _emoji = i_emoji.Emoji(file_=self[_idx], name=_name, url=_url)
            _emojis.append(_emoji)
        return tuple(_emojis)

    @cache_method_to_file
    def _to_parser_data(self, force=False):
        """Obtain data by parsing index.html file.

        Args:
            force (bool): force reread index.html from disk

        Returns:
            (tuple list): index/name/url
        """

        # Parse html
        _hook = codecs.open(self.index, encoding='utf-8')
        _body = _hook.read()
        _hook.close()
        _parser = i_parser.EmojiIndexParser()
        _parser.feed(_body)

        # Organise data
        _data = []
        for _raw_name, _idx in _parser.names.items():
            _name = _raw_name.strip()
            _LOGGER.debug('NAME / IDX %s %d', _name, _idx)
            if not _name:
                _LOGGER.debug(' - REJECTED NO NAME')
                continue
            _url = _parser.urls[_raw_name]
            if _url:
                _url = _url.strip()
            _data.append((_idx, _name, _url))

        return _data
