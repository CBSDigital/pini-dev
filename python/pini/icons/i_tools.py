"""Tools for managing icons."""

import functools
import logging

from pini.utils import is_abs

from . import i_const

_LOGGER = logging.getLogger(__name__)


@functools.wraps(i_const.EMOJI.find)
def find(*args, **kwargs):
    """Find the path to an emoji in the default set.

    Args:
        match (str|int): match by name or index
        catch (bool): no error if exactly one emoji is not found
        verbose (int): print process data

    Returns:
        (str): path to emoji
    """
    return i_const.EMOJI.find(*args, **kwargs)


@functools.wraps(i_const.EMOJI.find_emoji)
def find_emoji(*args, **kwargs):
    """Find an emoji in the default set.

    Args:
        match (str|int): match by name or index
        catch (bool): no error if exactly one emoji is not found
        verbose (int): print process data

    Returns:
        (Emoji): matching emoji
    """
    return i_const.EMOJI.find_emoji(*args, **kwargs)


@functools.wraps(i_const.EMOJI.find_grp)
def find_grp(*args, **kwargs):
    """Find a named group of emojis within the default set.

    Args:
        name (str): name of group (eg. fruit)

    Returns:
        (str list): list of emoji paths
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
