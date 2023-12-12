"""General utilities relating to filters.

This is a simplified text filter based on google search.

eg. apply_filter(['aaa', 'bbb', 'ccc'], 'aaa') -> ['aaa']
    apply_filter(['aaa', 'bbb', 'ccc'], '-aaa') -> ['bbb', 'ccc']
"""

import logging

from .u_heart import check_heart

_LOGGER = logging.getLogger(__name__)


def apply_filter(items, filter_, key=None):
    """Apply a filter to a list of items.

    Args:
        items (list): items to filter
        filter_ (str): filter to apply
        key (func): function to convert item to filterable text

    Returns:
        (list): list of items which pass filter
    """
    _results = []
    for _item in items:
        if key:
            _text = key(_item)
        else:
            _text = _item
        if passes_filter(_text, filter_):
            _results.append(_item)

    return _results


def _required_tokens_missing(text, required_tokens):
    """Check whether any required tokens are missing.

    Args:
        text (str): text to check
        required_tokens (str list): required tokens

    Returns:
        (bool): whether missing required tokens fails filter
    """
    if not required_tokens:
        return True
    _LOGGER.debug(' - TESTING REQUIRED %s', required_tokens)
    for _token in required_tokens:
        _LOGGER.debug('   - TEST TOKEN %s', _token)
        if _token not in text:
            _LOGGER.debug(' - FAILED DUE TO MISSING REQUIRED')
            return False
    return True


def _ignore_tokens_present(text, ignore_tokens):
    """Test whether any ignore tokens are present.

    Args:
        text (str): text to check
        ignore_tokens (str list): ignore tokens

    Returns:
        (bool): whether ignore tokens cause filter to fail
    """
    if not ignore_tokens:
        return False
    _LOGGER.debug(' - TESTING IGNORE %s', ignore_tokens)
    for _token in ignore_tokens:
        _LOGGER.debug('   - TEST TOKEN %s', _token)
        if _token in text:
            _LOGGER.debug(' - FAILED DUE TO IGNORE')
            return True
    return False


def passes_filter(text, filter_, case_sensitive=False):
    """Check if the given text passes the given filter.

    Args:
        text (str): text to check
        filter_ (str): filter to apply
        case_sensitive (bool): filter is case sensitive

    Returns:
        (bool): whether text passes filter
    """
    check_heart()
    _LOGGER.debug('PASSES FILTER %s %s', text, filter_)
    if not filter_:
        return True

    _text = text
    _filter = filter_
    if not case_sensitive:
        _text = _text.lower()
        _filter = _filter.lower()

    # Parse tokens
    _tokens = _filter.split()
    _match_tokens, _ignore_tokens, _required_tokens = [], [], []
    for _token in _tokens:
        if _token[0] == '-':
            _ignore_tokens.append(_token[1:])
        elif _token[0] == '+':
            _required_tokens.append(_token[1:])
        else:
            _match_tokens.append(_token)

    if not _required_tokens_missing(
            text=_text, required_tokens=_required_tokens):
        return False
    if _ignore_tokens_present(
            text=_text, ignore_tokens=_ignore_tokens):
        return False

    # Apply straightforward match
    if _match_tokens:
        _LOGGER.debug(' - TESTING MATCH %s', _match_tokens)
        for _token in _match_tokens:
            if _token in _text:
                _LOGGER.debug('   - MATCHED %s', _token)
                return True
        return False

    return True
