"""Tools for managing icons."""

import functools
import logging

from pini.utils import is_abs

from . import i_const

_LOGGER = logging.getLogger(__name__)


@functools.wraps(i_const.EMOJI.find)
def find(*args, **kwargs):
    """Find an emoji path from the default set.

    Returns:
        (str): path to matching emoji
    """
    return i_const.EMOJI.find(*args, **kwargs)


@functools.wraps(i_const.EMOJI.find_emoji)
def find_emoji(*args, **kwargs):
    """Find an emoji from the default set.

    Returns:
        (Emoji): path to matching emoji
    """
    return i_const.EMOJI.find_emoji(*args, **kwargs)


@functools.wraps(i_const.EMOJI.find_grp)
def find_grp(*args, **kwargs):
    """Find a group of emojis (eg. fruit).

    Returns:
        (str list): emojis in group
    """
    return i_const.EMOJI.find_grp(*args, **kwargs)


def to_icon(match):
    """Obtain an icon from the given token.

    Args:
        match (str): icon path/name/index

    Returns:
        (str): path to icon
    """
    if is_abs(match):
        return match
    _name_match = i_const.EMOJI.find(match)
    if _name_match:
        return _name_match
    raise NotImplementedError(match)
