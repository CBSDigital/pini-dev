"""Tools for managing callbacks."""

import logging
import types

from .u_text import is_pascal

_LOGGER = logging.getLogger(__name__)

_APPROVED_TYPES = (
    'CreateRef',
    'HelperWorkIcon',
    'Publish',
    'ReadSettings',
    'SelectEntity',
    'SetWork',
    'Test',
)
CALLBACKS = {}


def install_callback(type_, func):
    """Install callback into the pipeline.

    This should be called at global level in a startup module so that
    it survives a reload.

    Args:
        type_ (str): callback type (eg. SetWork/ReadSettings)
        func (fn): callback function
    """
    assert is_pascal(type_)
    if type_ not in _APPROVED_TYPES:
        raise RuntimeError(f'Unapproved callback type "{type_}"')
    if func:
        assert isinstance(func, types.FunctionType)
        CALLBACKS[type_] = func
        _LOGGER.debug('INSTALLED CALLBACK %s %s', type_, func)
    elif func is None:
        CALLBACKS.pop(type_, None)
        _LOGGER.debug('UNINSTALLED CALLBACK %s %s', type_, func)
    else:
        raise ValueError(func)


def find_callback(type_):
    """Find an installed callback.

    Args:
        type_ (str): callback type (eg. SetWork/ReadSettings)

    Returns:
        (fn|None): installed callback (if any)
    """
    return CALLBACKS.get(type_)
