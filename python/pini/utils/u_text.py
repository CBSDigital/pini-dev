"""Tools for managing text."""

import logging
import re

_LOGGER = logging.getLogger(__name__)
_SPLIT_RX = r'[ \-_\[\]\n:\(\)]'


def add_indent(text, indent='    '):
    """Add indent to the given lines of text.

    Args:
        text (str): text to indent
        indent (str): indent to apply

    Returns:
        (str): indented text
    """
    return indent + (text.replace('\n', '\n'+indent))


def copy_text(text, verbose=1):
    """Copy the given text to clipboard.

    Args:
        text (str): text to copy
        verbose (int): print process data
    """
    from pini import qt
    from pini.qt import QtWidgets
    from pini.utils import lprint

    # Apply text to clipboard
    _app = qt.get_application()
    if isinstance(_app, QtWidgets.QApplication):
        _clip = _app.clipboard()
        _clip.setText(text)
        _tag = '[copied]'
    else:
        _LOGGER.info('Failed to copy due to bad QApplication: %s', _app)
        _tag = '[text]'

    # Print copied text
    if '\n' in text:
        lprint(_tag, verbose=verbose)
        lprint(text, verbose=verbose)
    else:
        lprint(_tag, text, verbose=verbose)


def is_camel(text):
    """Test if the given text in camel case.

    Args:
        text (str): text to check

    Returns:
        (bool): whether text is camel case
    """
    if not text:
        return False
    if ' ' in text:
        return False
    if text[0].isupper():
        return False
    return True


def is_pascal(text):
    """Test whether the given text is pascal (eg. SomeText).

    Args:
        text (str): text to check

    Returns:
        (bool): whether valid pascal case
    """
    if not text:
        return False
    if not text[0].isupper():
        return False
    for _chr in ' _':
        if _chr in text:
            return False
    return True


def plural(items, singular='', plural_='s'):
    """Return a plural character if there is not exactly one item.

    If there is one item, the singular returned.

    Args:
        items (list|int): list/count to check
        singular (str): override value to return on singular
        plural_ (str): override value to return on plural

    Returns:
        (str): plural character if requires
    """
    _plural = plural_ or 's'
    if isinstance(items, (list, tuple, set)):
        _is_plural = len(items) != 1
    elif isinstance(items, int):
        _is_plural = items != 1
    else:
        raise ValueError(items)
    return _plural if _is_plural else singular


def split_base_index(string):
    """Break a string into base and index tokens.

    If the string doesn't end with an digit then the index is zero.

    eg. blah20 -> blah, 20
        blah -> blah. -

    Args:
        string (str): string to parse

    Returns:
        (str): comparison string
    """
    _base = string
    _idx_str = ''
    while _base and _base[-1].isdigit():
        _idx_str = _base[-1]+_idx_str
        _base = _base[:-1]

    _idx = int(_idx_str) if _idx_str else 0
    return _base, _idx


def to_camel(text):
    """Convert the given text to camel case.

    eg. some test text -> someTestText
        some_test_text -> someTestText

    Args:
        text (str): text to convert

    Returns:
        (str): text in camel case
    """
    _tokens = re.split(_SPLIT_RX, text)
    _camel = ''
    for _idx, _token in enumerate(_tokens):
        if _idx:
            _token = _token[0].upper()+_token[1:]
        else:
            _token = _token[0].lower()+_token[1:]
        _camel += _token
    return _camel


def to_nice(text):
    """Convert camel/snake text to a readable string.

    eg. someTestText -> some test text
        some_test_text -> some test text

    Args:
        text (str): text to convert

    Returns:
        (str): readable text
    """
    _nice = ''
    for _chr in text:
        if _chr in '_':
            _nice += ' '
            continue
        if _chr.isupper():
            _nice += ' '
        _nice += _chr.lower()
    _nice = ' '.join(_nice.split())  # Remove double spaces
    return _nice.strip()


def to_ord(number):
    """Get ordinal suffix for the given number.

    eg. 1 -> "st"
        2 -> "nd"
        10 -> "th"

    Args:
        number (int): number to get ordinal for

    Returns:
        (str): ordinal suffix
    """
    if number % 10 == 1 and not str(number).endswith('11'):
        return 'st'
    if number % 10 == 2 and not str(number).endswith('12'):
        return 'nd'
    if number % 10 == 3 and not str(number).endswith('13'):
        return 'rd'
    return 'th'


def to_pascal(text):
    """Convert the given test to pascal.

    eg. blah_blah -> BlahBlah

    Args:
        text (str): text to convert

    Returns:
        (str): converted text
    """
    _LOGGER.debug('TO PASCAL %s', text)
    _tokens = [_token for _token in re.split(_SPLIT_RX, text) if _token]
    _LOGGER.debug(' - TOKENS %s', _tokens)
    _result = ''.join([_token[0].upper()+_token[1:] for _token in _tokens])
    _LOGGER.debug(' - RESULT %s', _result)
    return _result


def to_snake(text):
    """Convert the given text to snake case.

    eg. ThisIsSomeText -> this_is_some_text
        This Is Some Text -> this_is_some_text

    Args:
        text (str): text to convert

    Returns:
        (str): snake case text
    """
    _LOGGER.debug('TO SNAKE')
    _text = ' '.join(text.split())
    _LOGGER.debug(' - TEXT "%s"', _text)

    _out = ''
    for _idx, _chr in enumerate(_text):
        if _chr.isupper():
            _out += '_'+_chr.lower()
        elif _chr == ' ':
            _out += '_'
        else:
            _out += _chr.lower()

    return _out.strip('_').replace('__', '_')
